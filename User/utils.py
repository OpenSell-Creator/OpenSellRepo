def user_directory_path(instance, filename):
    return f'profile_pictures/{instance.user.username}/{filename}'