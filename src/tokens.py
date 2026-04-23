# src/tokens.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Modern version - no 'six' needed
        return (
            str(user.pk) +
            str(timestamp) +
            str(user.email_verified)
        )


# Global instance (we'll import this)
email_verification_token = EmailVerificationTokenGenerator()