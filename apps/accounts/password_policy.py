from django.core.exceptions import ValidationError

from apps.common.preferences import preferences


class PortalPasswordValidator:
    def validate(self, password, user=None):
        config = preferences()
        minimum = config['minimum_password_length']
        if len(password) < minimum:
            raise ValidationError(f'Use at least {minimum} characters.', code='portal_password_length')
        if config.get('password_complexity'):
            checks = (str.isupper, str.islower, str.isdigit, lambda char: not char.isalnum() and not char.isspace())
            if not all(any(check(char) for char in password) for check in checks):
                raise ValidationError('Include uppercase and lowercase letters, a number, and a symbol.', code='portal_password_complexity')

    def get_help_text(self):
        return 'Follow the password length and complexity requirements set by your administrator.'
