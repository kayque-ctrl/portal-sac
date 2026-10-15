import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class Papel(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    OPERADOR = "operador", "Operador"
    ADMIN = "admin", "Admin"


class TipoPessoa(models.TextChoices):
    PF = "pf", "Pessoa física"
    PJ = "pj", "Pessoa jurídica"
    FUNCIONARIO = "funcionario", "Funcionário"


class Empresa(models.Model):
    """Empresa cliente à qual um usuário do tipo cliente pode pertencer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200, db_index=True)
    cnpj = models.CharField(max_length=30, blank=True, null=True)
    contato_nome = models.CharField(max_length=200, blank=True, null=True)
    contato_email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=40, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _criar(self, email, password, **extra):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        extra.setdefault("nome", email)
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            # Convite: sem senha até o usuário definir pelo link.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        # Todo usuário nasce como cliente; promoção é ação separada.
        extra.setdefault("papel", Papel.CLIENTE)
        return self._criar(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        from django.utils import timezone

        extra.setdefault("papel", Papel.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("ativado_em", timezone.now())
        return self._criar(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """
    Usuário do sistema (antes: auth.users + public.profiles do Supabase).
    Login por e-mail. O papel define a área: cliente → /portal, operador e
    admin → /operacao (admin é um operador com poderes extras).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=200)
    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.CLIENTE, db_index=True)
    tipo_pessoa = models.CharField(max_length=12, choices=TipoPessoa.choices, blank=True, null=True)
    documento = models.CharField(max_length=30, blank=True, null=True)
    telefone = models.CharField(max_length=40, blank=True, null=True)
    empresa = models.ForeignKey(
        Empresa, on_delete=models.SET_NULL, null=True, blank=True, related_name="membros"
    )
    # Quando definiu a senha pela primeira vez (aceitou o convite). Nulo = pendente.
    ativado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Acesso ao /admin do Django.")

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        ordering = ["nome"]
        verbose_name = "usuário"

    def __str__(self) -> str:
        return self.nome or self.email

    @property
    def eh_operacao(self) -> bool:
        """Tem acesso à área de operação (operador ou admin)."""
        return self.papel in (Papel.OPERADOR, Papel.ADMIN)

    @property
    def eh_admin(self) -> bool:
        """Configura SLA, gerencia papéis e a lixeira."""
        return self.papel == Papel.ADMIN

    @property
    def eh_cliente(self) -> bool:
        return self.papel == Papel.CLIENTE

    @property
    def primeiro_nome(self) -> str:
        return (self.nome or "").split(" ")[0]
