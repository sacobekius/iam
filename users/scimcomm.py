import requests, datetime, time
from urllib.parse import urljoin
from users.models import User
from django.contrib.auth.models import Group

def scimtime(time):
    return time.strftime('%Y-%m-%dT%H:%M:%S')

class EndOfProcess(Exception):
    def __init__(self, response: requests.Response, sync_point):
        self.response = response
        sync_point.last_request = response.request.url
        sync_point.last_request_body = response.request.body
        sync_point.last_response = response.text
        sync_point.last_result = response.reason
        sync_point.save()

class SCIMComm:

    def __init__(self, sync_point):
        self.sync_point = sync_point
        self.session = requests.Session()
        self.state = {}
        self.session.headers.update({
            'Authorization': 'Bearer %s' % self.sync_point.auth_token,
            'User-Agent': 'Autorisatie STUB',
            'Accept': 'application/json',
        })

    def _get_url(self, resource_path: str):

        url = urljoin(self.sync_point.url, 'scim/v2/')
        url = urljoin(url, resource_path)

        return url

    def _process_response(self, response: requests.Response, expected: list = []) -> dict:
        responses = {
            200: None,
            201: None,
            204: None,
        }

        if response.status_code not in expected and response.status_code not in responses.keys():
                raise EndOfProcess(response, self.sync_point)
        try:
            data = response.json()
        except ValueError:
            data = response.text

        return data

    def get(self, resource_path: str):
        response = self.session.get(url=self._get_url(resource_path),)
        return self._process_response(response)

    def post(self, resource_path: str, data: dict):
        response = self.session.post(url=self._get_url(resource_path), json=data)
        return self._process_response(response, [201])

    def patch(self, resource_path: str, data: dict):
        response = self.session.patch(url=self._get_url(resource_path), json=data)
        return self._process_response(response, [201])

    def delete(self, resource_path: str):
        response = self.session.delete(url=self._get_url(resource_path))
        return self._process_response(response, [204])


class SCIMObjects:
    def __init__(self, process, endpoint, resource):
        self.process = process
        self.endpoint = endpoint
        self.resource = resource
        self.objects = {}
        for item in self.endpoint.get(resource)['Resources']:
            self.objects[item['id']] = item

    def __getitem__(self, key):
        return self.objects[key]

    def __setitem__(self, key, value):
        self.objects[key] = value

    def keys(self):
        return self.objects.keys()

    def getbyexternalid(self, externalid):
        for scim_id in self.objects.keys():
            if self.objects[scim_id]['externalId'] == externalid:
                return scim_id
        raise ValueError(f'SCIMObject {externalid} not found')

    def delSCIM(self, key):
        self.endpoint.delete(f'{self.resource}/{key}')
        del self.objects[key]


class SCIMGroups(SCIMObjects):

    def __init__(self, process, endpoint):
        super().__init__(process, endpoint, 'Groups')

    def newSCIM(self, group):
        first_user = group.user_set.first()
        scim_representation = {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
            "created": scimtime(first_user.date_joined) if first_user else scimtime(datetime.datetime.now()),
            "lastModified": scimtime(datetime.datetime.now()),
            "displayName": group.name,
            "members": [
            ],
            "externalId": str(group.id),
            "version": None,
        }
        new_object = self.endpoint.post('Groups', scim_representation)
        self.objects[new_object['id']] = self.endpoint.get(f'Groups/{new_object['id']}')
        self.patchMembers(new_object['id'], group.user_set.all())

    def checkSCIM(self, group):
        key = self.getbyexternalid(str(group.id))
        object_by_key = self.endpoint.get(f'Groups/{key}')
        if self.objects[key]['displayName'] != group.name:
            self.endpoint.patch(f'Groups/{key}', {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "replace",
                        "value": group.name,
                        "path": "displayName"
                    }
                ]
            })
        self.patchMembers(key, group.user_set.all())

    def patchMembers(self, key, users):
        users_found = ()
        if 'members' in self.objects[key].keys():
            for member in self.objects[key]['members']:
                scim_user = self.process.users[member['value'].split('/')[-1]]
                try:
                    found_user = users.get(id=scim_user['externalId'])
                    users_found += (found_user.id,)
                except User.DoesNotExist:
                    self.endpoint.patch('Groups', {
                        "Operations": [
                            {
                                "op": "remove",
                                "path": f"members[value eq \"{scim_user['id']}\"]"
                            }
                        ],
                        "schemas": [
                            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                        ]
                    })
                    self.objects[key] = self.endpoint.get('Groups', key)
        user_list = []
        for user in users:
            user_list.append({"value": f"{self.process.users.getbyexternalid(str(user.id))}"})
        new_object = self.endpoint.patch(f'Groups/{key}', {
                    "Operations": [
                        {
                            "op": "add",
                            "value": user_list,
                            "path": "members"
                        }
                    ],
                    "schemas": [
                        "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                    ]
                })
#        for user in users:
#            if user.id not in users_found:
#                scim_id = self.process.users.getbyexternalid(str(user.id))
#                new_object = self.endpoint.patch(f'Groups/{key}', {
#                    "Operations": [
#                        {
#                            "op": "add",
#                            "value": [
#                                {
#                                    "value": f"{scim_id}"
#                                },
#                            ],
#                            "path": "members"
#                        }
#                    ],
#                    "schemas": [
#                        "urn:ietf:params:scim:api:messages:2.0:PatchOp"
#                    ]
#                })
        self.objects[key] = self.endpoint.get(f'Groups/{key}')


class SCIMUsers(SCIMObjects):

    def __init__(self, process, endpoint):
        super().__init__(process, endpoint, 'Users')

    def checkSCIM(self, user):
        pass

    def newSCIM(self, user):
        scim_representation = {
            "active": user.is_active,
            "created": scimtime(user.date_joined),
            "lastModified": scimtime(datetime.datetime.now()),
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "externalId": str(user.id),
            "userName": user.username,
            "displayName": f'{user.first_name} {user.last_name}',
        }
        new_object = self.endpoint.post('Users', scim_representation)
        self.objects[new_object['id']] = new_object


class SCIMProcess:

    def __init__(self, sync_point):
        self.groups = None
        self.users = None
        self.endpoint = SCIMComm(sync_point)

    def process(self):
        try:
            self.users = SCIMUsers(self, self.endpoint)
            self.groups = SCIMGroups(self, self.endpoint)

            users_found = ()
            for scim_user in self.users.keys():
                try:
                    user = User.objects.get(id=self.users[scim_user]['externalId'])
                    self.users.checkSCIM(user)
                    users_found += (user.id,)
                except (User.DoesNotExist, ValueError):
                    self.users.delSCIM(scim_user)
                    self.endpoint.delete(f'Users/{scim_user['id']}')
            for user in User.objects.all():
                if user.id not in users_found:
                    self.users.newSCIM(user)

            groups_found = ()
            for scim_group in self.groups.keys():
                try:
                    group = Group.objects.get(id=self.groups[scim_group]['externalId'])
                    self.groups.checkSCIM(group)
                    groups_found += (group.id,)
                except (ValueError, KeyError):
                    self.groups.delSCIM(scim_group)
            for group in Group.objects.all():
                if group.id not in groups_found:
                    self.groups.newSCIM(group)

        except EndOfProcess:
            return False
        return True

    def clear(self):
        try:
            self.users = SCIMUsers(self, self.endpoint)
            self.groups = SCIMGroups(self, self.endpoint)

            user_keys = list(self.users.keys())
            for scim_user in user_keys:
                self.users.delSCIM(scim_user)
            group_keys = list(self.groups.keys())
            for scim_id in group_keys:
                self.groups.delSCIM(scim_id)
        except EndOfProcess:
            return False
        return True

