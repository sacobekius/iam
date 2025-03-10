from oauth2_provider.oauth2_validators import OAuth2Validator

class CustomOAuth2Validator(OAuth2Validator):

    def get_additional_claims(self, request):
        return {
            'username': request.user.email,
            'email': request.user.email,
            'userPrincipalName': request.user.email,
        }

    def get_userinfo_claims(self, request):
        claims = super().get_userinfo_claims(request)
        claims['username'] = request.user.email
        claims['email'] = request.user.email
        claims['givenName'] = request.user.first_name,
        claims['surname'] = request.user.last_name,
        claims['displayName'] = ' '.join([request.user.first_name, request.user.last_name]),
        return claims
