# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class HomeBrand(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)
    slug = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Home_brand'


class HomeBrandCategories(models.Model):
    id = models.BigAutoField(primary_key=True)
    brand = models.ForeignKey(HomeBrand, models.DO_NOTHING)
    category = models.ForeignKey('HomeCategory', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Home_brand_categories'
        unique_together = (('brand', 'category'),)


class HomeBrandSubcategories(models.Model):
    id = models.BigAutoField(primary_key=True)
    brand = models.ForeignKey(HomeBrand, models.DO_NOTHING)
    subcategory = models.ForeignKey('HomeSubcategory', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Home_brand_subcategories'
        unique_together = (('brand', 'subcategory'),)


class HomeCategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=100)
    slug = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Home_category'


class HomeProductImage(models.Model):
    id = models.UUIDField(primary_key=True)
    image = models.CharField(max_length=100)
    is_primary = models.BooleanField()
    product = models.ForeignKey('HomeProductListing', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Home_product_image'


class HomeProductListing(models.Model):
    id = models.UUIDField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    condition = models.CharField(max_length=4)
    brand = models.ForeignKey(HomeBrand, models.DO_NOTHING, blank=True, null=True)
    category = models.ForeignKey(HomeCategory, models.DO_NOTHING)
    location = models.OneToOneField('UserLocation', models.DO_NOTHING, blank=True, null=True)
    seller = models.ForeignKey('UserProfile', models.DO_NOTHING)
    subcategory = models.ForeignKey('HomeSubcategory', models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Home_product_listing'


class HomeSubcategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100, blank=True, null=True)
    category = models.ForeignKey(HomeCategory, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Home_subcategory'
        unique_together = (('category', 'name'),)


class MessagesConversation(models.Model):
    id = models.BigAutoField(primary_key=True)
    updated_at = models.DateTimeField()
    product = models.ForeignKey(HomeProductListing, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Messages_conversation'


class MessagesConversationParticipants(models.Model):
    id = models.BigAutoField(primary_key=True)
    conversation = models.ForeignKey(MessagesConversation, models.DO_NOTHING)
    profile = models.ForeignKey('UserProfile', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Messages_conversation_participants'
        unique_together = (('conversation', 'profile'),)


class MessagesMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    content = models.TextField()
    timestamp = models.DateTimeField()
    is_read = models.BooleanField()
    inquiry_type = models.CharField(max_length=20)
    conversation = models.ForeignKey(MessagesConversation, models.DO_NOTHING)
    sender = models.ForeignKey('UserProfile', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Messages_message'


class NotificationsNotification(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(max_length=20)
    is_read = models.BooleanField()
    created_at = models.DateTimeField()
    object_id = models.CharField(max_length=36, blank=True, null=True)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    recipient = models.ForeignKey('AuthUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Notifications_notification'


class NotificationsNotificationpreference(models.Model):
    id = models.BigAutoField(primary_key=True)
    review_notifications = models.BooleanField()
    save_notifications = models.BooleanField()
    view_milestone_notifications = models.BooleanField()
    system_notifications = models.BooleanField()
    deletion_warnings = models.BooleanField()
    stock_alerts = models.BooleanField()
    user = models.OneToOneField('AuthUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'Notifications_notificationpreference'


class UserLocation(models.Model):
    id = models.BigAutoField(primary_key=True)
    address = models.CharField(max_length=120)
    address_2 = models.CharField(max_length=120)
    district = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    city = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'User_location'


class UserProfile(models.Model):
    id = models.BigAutoField(primary_key=True)
    photo = models.CharField(max_length=100, blank=True, null=True)
    bio = models.CharField(max_length=225)
    phone_number = models.CharField(max_length=12)
    user = models.OneToOneField('AuthUser', models.DO_NOTHING)
    location = models.OneToOneField(UserLocation, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'User_profile'


class AccountEmailaddress(models.Model):
    email = models.CharField(unique=True, max_length=254)
    verified = models.BooleanField()
    primary = models.BooleanField()
    user = models.ForeignKey('AuthUser', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'account_emailaddress'
        unique_together = (('user', 'email'), ('user', 'primary'),)


class AccountEmailconfirmation(models.Model):
    created = models.DateTimeField()
    sent = models.DateTimeField(blank=True, null=True)
    key = models.CharField(unique=True, max_length=64)
    email_address = models.ForeignKey(AccountEmailaddress, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'account_emailconfirmation'


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class DjangoSite(models.Model):
    domain = models.CharField(unique=True, max_length=100)
    name = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'django_site'


class SocialaccountSocialaccount(models.Model):
    provider = models.CharField(max_length=200)
    uid = models.CharField(max_length=191)
    last_login = models.DateTimeField()
    date_joined = models.DateTimeField()
    extra_data = models.JSONField()
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'socialaccount_socialaccount'
        unique_together = (('provider', 'uid'),)


class SocialaccountSocialapp(models.Model):
    provider = models.CharField(max_length=30)
    name = models.CharField(max_length=40)
    client_id = models.CharField(max_length=191)
    secret = models.CharField(max_length=191)
    key = models.CharField(max_length=191)
    provider_id = models.CharField(max_length=200)
    settings = models.JSONField()

    class Meta:
        managed = False
        db_table = 'socialaccount_socialapp'


class SocialaccountSocialappSites(models.Model):
    id = models.BigAutoField(primary_key=True)
    socialapp = models.ForeignKey(SocialaccountSocialapp, models.DO_NOTHING)
    site = models.ForeignKey(DjangoSite, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'socialaccount_socialapp_sites'
        unique_together = (('socialapp', 'site'),)


class SocialaccountSocialtoken(models.Model):
    token = models.TextField()
    token_secret = models.TextField()
    expires_at = models.DateTimeField(blank=True, null=True)
    account = models.ForeignKey(SocialaccountSocialaccount, models.DO_NOTHING)
    app = models.ForeignKey(SocialaccountSocialapp, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'socialaccount_socialtoken'
        unique_together = (('app', 'account'),)
