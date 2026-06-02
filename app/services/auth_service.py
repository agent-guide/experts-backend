from dataclasses import dataclass, field
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import hash_password, issue_token_pair, verify_password
from app.domain.auth import Principal, Role, role_permissions


@dataclass
class UserRecord:
    id: str
    tenant_id: str
    email: str
    name: str
    password_hash: str
    roles: list[Role] = field(default_factory=lambda: [Role.USER])
    status: str = "active"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._users_by_email: dict[str, UserRecord] = {}
        self._users_by_id: dict[str, UserRecord] = {}

    def register(self, email: str, password: str, name: str) -> dict[str, object]:
        normalized = email.strip().lower()
        if normalized in self._users_by_email:
            raise ApiError(409, "AUTH_EMAIL_EXISTS", "Email already registered")
        user = UserRecord(
            id=f"user_{uuid4().hex}",
            tenant_id=self.settings.default_tenant_id,
            email=normalized,
            name=name,
            password_hash=hash_password(password),
        )
        self._users_by_email[normalized] = user
        self._users_by_id[user.id] = user
        return issue_token_pair(self.settings, self._principal(user))

    def login(self, email: str, password: str) -> dict[str, object]:
        user = self._users_by_email.get(email.strip().lower())
        if not user or not verify_password(password, user.password_hash):
            raise ApiError(401, "AUTH_INVALID_CREDENTIALS", "Invalid email or password")
        if user.status != "active":
            raise ApiError(403, "AUTH_USER_DISABLED", "User is disabled")
        return issue_token_pair(self.settings, self._principal(user))

    def grant_role(self, target_user_id: str, role: Role) -> None:
        user = self._users_by_id.get(target_user_id)
        if not user:
            raise ApiError(404, "USER_NOT_FOUND", "User not found")
        if role not in user.roles:
            user.roles.append(role)

    def _principal(self, user: UserRecord) -> Principal:
        permissions = sorted({perm for role in user.roles for perm in role_permissions(role)})
        return Principal(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            roles=user.roles,
            permissions=permissions,
        )
