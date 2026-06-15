import json
import time
import uuid

from jwcrypto import jwt as jwcrypto_jwt
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.utils import jwk_from_pem


class CustomOAuth2Validator(OAuth2Validator):

    def get_additional_claims(self, request):
        return {
            'preferred_username': request.user.email,
            'email': request.user.email,
            'userPrincipalName': request.user.email,
        }

    def get_userinfo_claims(self, request):
        claims = super().get_userinfo_claims(request)
        claims['preferred_username'] = request.user.email
        claims['email'] = request.user.email
        claims['givenName'] = request.user.first_name
        claims['surname'] = request.user.last_name
        claims['displayName'] = ' '.join([request.user.first_name, request.user.last_name])
        claims['groups'] = list(request.user.groups.values_list('name', flat=True))
        return claims


def jwt_access_token_generator(request):
    """JWT access token in Entra-stijl, ondertekend met RS256.

    Bevat: iss, sub, aud (=client_id), scp, roles, groups, email, name.
    Valt terug op willekeurig token als OIDC_RSA_PRIVATE_KEY niet is geconfigureerd.
    """
    if not oauth2_settings.OIDC_RSA_PRIVATE_KEY:
        from oauthlib.oauth2.rfc6749.tokens import random_token_generator
        return random_token_generator(request)

    jwk_key = jwk_from_pem(oauth2_settings.OIDC_RSA_PRIVATE_KEY)
    now = int(time.time())
    expires_in = getattr(request, 'expires_in', None) or oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS

    roles = []
    groups = []
    if request.user:
        try:
            roles = list(
                request.user.rollen.filter(application=request.client)
                .values_list('name', flat=True)
            )
        except Exception:
            pass
        try:
            groups = list(request.user.groups.values_list('name', flat=True))
        except Exception:
            pass

    claims = {
        'iss': oauth2_settings.oidc_issuer(request),
        'sub': str(request.user.pk) if request.user else '',
        'aud': request.client.client_id if request.client else '',
        'iat': now,
        'exp': now + expires_in,
        'jti': str(uuid.uuid4()),
        'scp': ' '.join(request.scopes) if request.scopes else '',
        'preferred_username': getattr(request.user, 'email', ''),
        'email': getattr(request.user, 'email', ''),
        'name': f'{getattr(request.user, "first_name", "")} {getattr(request.user, "last_name", "")}'.strip(),
        'roles': roles,
        'groups': groups,
    }

    header = json.dumps({'typ': 'JWT', 'alg': 'RS256', 'kid': jwk_key.thumbprint()})
    token = jwcrypto_jwt.JWT(header=header, claims=json.dumps(claims, default=str))
    token.make_signed_token(jwk_key)
    return token.serialize()
