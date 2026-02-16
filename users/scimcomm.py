import requests, datetime, time
from urllib.parse import urljoin

from oauth2_provider.management.commands.createapplication import Application
from users.models import User, LocGroup
from django.db.models.signals import pre_save, pre_delete, m2m_changed, post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import Group


def scimtime(time):
    return time.strftime('%Y-%m-%dT%H:%M:%S')


class EndOfProcess(Exception):
    def __init__(self, response: requests.Response, sync_point, request = '', request_body = None):
        self.response = response
        sync_point.last_request = request
        sync_point.last_request_body = request_body if request_body else ''
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

    def _process_response(self, response: requests.Response, expected: list = None, request = '', request_body = None) -> dict:
        responses = [ 200, 201, 204, ]

        if expected:
            responses += expected
        if response.status_code not in responses:
            raise EndOfProcess(response, self.sync_point, request, request_body)
        try:
            data = response.json()
        except ValueError:
            data = response.text

        return data

    def get(self, resource_path: str):
        response = self.session.get(url=self._get_url(resource_path), )
        return self._process_response(response, request=self._get_url(resource_path))

    def post(self, resource_path: str, data: dict):
        response = self.session.post(url=self._get_url(resource_path), json=data)
        return self._process_response(response, [201], request=self._get_url(resource_path), request_body=data)

    def put(self, resource_path: str, data: dict):
        response = self.session.put(url=self._get_url(resource_path), json=data)
        return self._process_response(response, [201], request=self._get_url(resource_path), request_body=data)

    def patch(self, resource_path: str, data: dict):
        response = self.session.patch(url=self._get_url(resource_path), json=data)
        return self._process_response(response, [201], request=self._get_url(resource_path), request_body=data)

    def delete(self, resource_path: str):
        response = self.session.delete(url=self._get_url(resource_path))
        return self._process_response(response, [204], request=self._get_url(resource_path))


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


@receiver(pre_save, sender=LocGroup)
@receiver(pre_delete, sender=LocGroup)
def group_handler(sender, instance, **kwargs):
    relevant_syncpoints = []
    try:
        for user in instance.user_set.all():
            try:
                if user.application:
                    if user.application.application_syncpoint:
                        if user.application.application_syncpoint not in relevant_syncpoints:
                            relevant_syncpoints.append(user.application.application_syncpoint)
            except Application.application_syncpoint.RelatedObjectDoesNotExist:
                pass
    except ValueError:
        pass
    for syncpoint in relevant_syncpoints:
        to_sync = SCIMProcess(syncpoint)
        to_sync.process()


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
        self.objects[new_object['id']] = self.endpoint.get(f"Groups/{new_object['id']}")
        self.patchMembers(new_object['id'], group.user_set.all())

    def checkSCIM(self, group):
        key = self.getbyexternalid(str(group.id))
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
            self.objects[key] = self.endpoint.get(f'Groups/{key}')
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
                    self.endpoint.patch(f'Groups/{key}', {
                        "Operations": [
                            {
                                "op": "remove",
                                "path": f'members[value eq "{scim_user["id"]}"]',
                            }
                        ],
                        "schemas": [
                            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                        ]
                    })
                    self.objects[key] = self.endpoint.get(f'Groups/{key}')
        user_list = []
        for user in users.filter(application__name__exact=self.endpoint.sync_point.application.name):
            if user.id not in users_found:
                user_list.append({"value": f"{self.process.users.getbyexternalid(str(user.id))}"})
        if len(user_list) > 0:
            self.endpoint.patch(f'Groups/{key}', {
                "Operations": [
                    {
                        "op": "add",
                        "value": user_list,
                        "path": "members",
                    }
                ],
                "schemas": [
                    "urn:ietf:params:scim:api:messages:2.0:PatchOp"
                ]
            })
            self.objects[key] = self.endpoint.get(f'Groups/{key}')


@receiver(m2m_changed, sender=User.locgroup.through)
def set_dirty_after_group_change(sender, instance, **kwargs):
    if 'action' in kwargs.keys() and kwargs['action'] in ['post_add', 'post_remove']:
        if type(instance) == User and instance.application and hasattr(instance.application, 'application_syncpoint'):
            to_sync = SCIMProcess(instance.application.application_syncpoint)
            to_sync.process()
            instance.application.application_syncpoint.dirty = False
            instance.application.application_syncpoint.save()


@receiver(pre_save, sender=User)
@receiver(pre_delete, sender=User)
def user_pre_handler(sender, instance, **kwargs):
    if 'action' in kwargs.keys() and kwargs['action'] in ['pre_add', 'pre_remove']:
        return
    if type(instance) == User and instance.application and hasattr(instance.application, 'application_syncpoint'):
        try:
            curr_user = User.objects.get(id=instance.id)
            instance.application.application_syncpoint.dirty |= curr_user.username != instance.locusername or \
                                                              curr_user.first_name != instance.first_name or \
                                                              curr_user.last_name != instance.last_name or \
                                                              curr_user.email != instance.email or \
                                                              curr_user.is_active != instance.is_active or \
                                                              curr_user.personeelsnummer != instance.personeelsnummer
        except User.DoesNotExist:
            instance.application.application_syncpoint.dirty |= True
        instance.application.application_syncpoint.save()


@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def user_post_handler(sender, instance, **kwargs):
    if 'action' in kwargs.keys() and kwargs['action'] in ['pre_add', 'pre_remove']:
        return
    if type(instance) == User and instance.application and hasattr(instance.application, 'application_syncpoint'):
        if instance.application.application_syncpoint.dirty:
            to_sync = SCIMProcess(instance.application.application_syncpoint)
            to_sync.process()
            instance.application.application_syncpoint.dirty = False
            instance.application.application_syncpoint.save()


class SCIMUsers(SCIMObjects):

    def __init__(self, process, endpoint):
        super().__init__(process, endpoint, 'Users')

    def checkSCIM(self, user):
        key = self.getbyexternalid(str(user.id))
        scim_representation = self.objects[key]
        if (
                scim_representation['displayName'] != f'{user.first_name} {user.last_name}' or
                scim_representation['userName'] != user.locusername or
                scim_representation['functionNumber'] != str(user.personeelsnummer) or
                scim_representation['active'] != user.is_active
        ):
            self.endpoint.patch(f'Users/{key}', {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "replace",
                        "value": user.locusername,
                        "path": "userName",
                    },
                    {
                        "op": "replace",
                        "value": str(user.personeelsnummer),
                        "path": "functionNumber",
                    },
                    {
                        "op": "replace",
                        "value": scimtime(user.date_joined),
                        "path": "created",
                    },
                    {
                        "op": "replace",
                        "value": scimtime(datetime.datetime.now()),
                        "path": "lastModified",
                    },
                    {
                        "op": "replace",
                        "value": f'{user.first_name} {user.last_name}',
                        "path": "displayName",
                    },
                    {
                        "op": "replace",
                        "value": user.is_active,
                        "path": "active",
                    },
                ]
            })
            self.objects[key] = self.endpoint.get(f'Users/{key}')

    def newSCIM(self, user):
        scim_representation = {
            "active": user.is_active,
            "created": scimtime(user.date_joined),
            "lastModified": scimtime(datetime.datetime.now()),
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "externalId": str(user.id),
            "userName": user.locusername,
            "functionNumber": str(user.personeelsnummer),
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
        if self.endpoint.sync_point.busy:
            if not self.endpoint.sync_point.hit_while_busy:
                self.endpoint.sync_point.hit_while_busy = True
                self.endpoint.sync_point.save()
            return True
        self.endpoint.sync_point.last_request = None
        self.endpoint.sync_point.last_result = None
        self.endpoint.sync_point.last_response = ''
        self.endpoint.sync_point.onverwachte_fout = None
        self.endpoint.sync_point.busy = True
        self.endpoint.sync_point.save()
        # Kans om LocGroup en Group te synchroniseren
        groupsrequired = ()
        for loc_group in LocGroup.objects.all():
            if loc_group.application:
                groupname = loc_group.application.name + '_' + loc_group.name
                groupsrequired += (groupname,)
                try:
                    group = Group.objects.get(name=groupname)
                    for loc_group_member in loc_group.user_set.all():
                        try:
                            group.user_set.get(username=loc_group_member.username)
                        except User.DoesNotExist:
                            group.user_set.add(loc_group_member)
                    for group_member in group.user_set.all():
                        try:
                            loc_group.user_set.get(username=group_member.username)
                        except User.DoesNotExist:
                            group.user_set.remove(group_member)
                    group.save()
                except Group.DoesNotExist:
                    group = Group.objects.create(name=groupname)
                    for loc_group_member in loc_group.user_set.all():
                        group.user_set.add(loc_group_member)
                    group.save()
            else:
                loc_group.delete()
        for group in Group.objects.all():
            if group.name not in groupsrequired:
                group.delete()

        # SCIM Synchronisatie
        result = False
        if self.endpoint.sync_point.active:
            result = True
            try:
                self.users = SCIMUsers(self, self.endpoint)
                self.groups = SCIMGroups(self, self.endpoint)

                while self.endpoint.sync_point.hit_while_busy:
                    self.endpoint.sync_point.hit_while_busy = False
                    self.endpoint.sync_point.save()
                    users_found = ()
                    scim_user_keys = list(self.users.keys())
                    for scim_user in scim_user_keys:
                        try:
                            user = User.objects.get(id=self.users[scim_user]['externalId'])
                            if user.application and user.application.name != self.endpoint.sync_point.application.name:
                                self.users.delSCIM(scim_user)
                            else:
                                self.users.checkSCIM(user)
                            users_found += (user.id,)
                        except (User.DoesNotExist, ValueError, KeyError):
                            self.users.delSCIM(scim_user)
                    for user in User.objects.filter(application__name__exact=self.endpoint.sync_point.application.name):
                        if user.id not in users_found:
                            self.users.newSCIM(user)

                    groups_found = ()
                    scim_group_keys = list(self.groups.keys())
                    for scim_group in scim_group_keys:
                        try:
                            group = LocGroup.objects.get(id=self.groups[scim_group]['externalId'])
                            if group.application and group.application.name != self.endpoint.sync_point.application.name:
                                self.groups.delSCIM(scim_group)
                            else:
                                self.groups.checkSCIM(group)
                            groups_found += (group.id,)
                        except (LocGroup.DoesNotExist, ValueError, KeyError):
                            self.groups.delSCIM(scim_group)
                    for group in LocGroup.objects.all():
                        if group.id not in groups_found:
                            self.groups.newSCIM(group)

            except EndOfProcess:
                result = False
            except Exception as e:
                result = False
                self.endpoint.sync_point.onverwachte_fout = str(e)
        self.endpoint.sync_point.busy = False
        self.endpoint.sync_point.save()
        return result

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
