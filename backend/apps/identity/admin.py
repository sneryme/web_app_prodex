from django.contrib import admin
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from rest_framework.authtoken.models import Token

from .models import AuditEvent, StaffProfile


class StaffProfileAdminForm(forms.ModelForm):
    username = forms.CharField(label="Логин", max_length=150)
    password = forms.CharField(
        label="Пароль",
        min_length=8,
        required=False,
        widget=forms.PasswordInput(render_value=False),
    )
    password_confirm = forms.CharField(
        label="Повторите пароль",
        required=False,
        widget=forms.PasswordInput(render_value=False),
    )

    class Meta:
        model = StaffProfile
        fields = ["role", "organization"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_model = get_user_model()
        self.fields["password"].help_text = (
            "Минимум 8 символов. При редактировании оставьте поле пустым, если пароль менять не нужно."
        )
        if self.instance.pk:
            self.fields["username"].initial = getattr(self.instance.user, user_model.USERNAME_FIELD)
        else:
            self.fields["role"].initial = StaffProfile.ROLE_ORG_ADMIN

    def clean_username(self):
        user_model = get_user_model()
        username = self.cleaned_data["username"]
        username_field = user_model.USERNAME_FIELD
        field = user_model._meta.get_field(username_field)
        field.clean(username, None)
        users = user_model._default_manager.filter(**{f"{username_field}__iexact": username})
        if self.instance.pk:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise ValidationError("Пользователь с таким логином уже существует.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password") or ""
        password_confirm = cleaned_data.get("password_confirm") or ""

        if not self.instance.pk and not password:
            self.add_error("password", "Введите пароль для новой учётной записи.")
        elif password and password != password_confirm:
            self.add_error("password_confirm", "Пароли не совпадают.")
        elif password_confirm and not password:
            self.add_error("password", "Введите новый пароль для подтверждения.")

        if password and password == password_confirm:
            user_model = get_user_model()
            username_field = user_model.USERNAME_FIELD
            candidate = self.instance.user if self.instance.pk else user_model()
            setattr(candidate, username_field, cleaned_data.get("username", ""))
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error("password", error)

        role = cleaned_data.get("role")
        organization = cleaned_data.get("organization")
        if role == StaffProfile.ROLE_ORG_ADMIN and organization is None:
            self.add_error("organization", "Для администратора работодателя выберите организацию.")
        elif role == StaffProfile.ROLE_PRODEX_ADMIN and organization is not None:
            self.add_error("organization", "Для администратора PRODEX организация не указывается.")

        return cleaned_data


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    form = StaffProfileAdminForm
    fields = ["username", "role", "organization", "password", "password_confirm", "created_at"]
    readonly_fields = ["created_at"]
    list_display = ["username", "role", "organization", "copy_employer_link", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__username", "user__email"]
    list_select_related = ["user", "organization"]

    class Media:
        js = ("organizations/admin.js",)

    @admin.display(description="Логин", ordering="user__username")
    def username(self, obj):
        return getattr(obj.user, get_user_model().USERNAME_FIELD)

    @admin.display(description="Кабинет работодателя")
    def copy_employer_link(self, obj):
        url = f"{settings.PARTICIPANT_FRONTEND_URL.rstrip('/')}/employer"
        return format_html(
            '<button type="button" class="button js-copy-entry-link" data-copy-url="{}">Ссылка для работодателя</button>',
            url,
        )

    def save_model(self, request, obj, form, change):
        user_model = get_user_model()
        username = form.cleaned_data["username"]
        password = form.cleaned_data.get("password")

        if obj.user_id:
            user = obj.user
            setattr(user, user_model.USERNAME_FIELD, username)
            if password:
                user.set_password(password)
            user.save()
            if password:
                # Password changes invalidate the existing API login immediately.
                Token.objects.filter(user=user).delete()
        else:
            user = user_model._default_manager.create_user(
                **{user_model.USERNAME_FIELD: username}, password=password
            )
            obj.user = user

        super().save_model(request, obj, form, change)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Журнал только на чтение: записи создаёт код (`identity/services.py`), не человек.

    `readonly_fields` сам по себе запрещает лишь правку полей — через админку всё ещё можно было
    бы добавить запись задним числом или удалить неудобную. Журнал, в котором можно дописать или
    стереть строку, не выполняет своей задачи (Положение о ролях, п. 5.3), поэтому добавление и
    удаление закрыты тоже. Правка не закрыта отдельным методом: все поля уже readonly.
    """

    list_display = ["created_at", "actor", "action", "target_type", "target_id"]
    list_filter = ["action", "target_type"]
    readonly_fields = ["actor", "action", "target_type", "target_id", "metadata", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
