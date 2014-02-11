from django.contrib.auth.models import User, Group

class ModelBackend(object):
    def authenticate(self, username=None, password=None):
        user = User.all().filter('username = ', username).get()
        if not user:
            user = User.all().filter('email =', username).get()
        if user and user.check_password(password):
            return user
        return None

    def get_group_permissions(self, user_obj):
        if not hasattr(user_obj, '_group_perm_cache'):
            if not user_obj.groups:
                return set()
            permissions = []
            for group in Group.get(user_obj.groups):
                if group:
                    permissions.extend(group.permissions)
            user_obj._group_perm_cache = set([
                '%s.%s' % (perm.content_type.app_label, perm.codename)
                for perm in permissions])
        return user_obj._group_perm_cache

    def get_all_permissions(self, user_obj):
        if not hasattr(user_obj, '_perm_cache'):
            user_obj._perm_cache = set([u"%s.%s" % (p.content_type.app_label, p.codename) for p in user_obj.user_permissions])
            user_obj._perm_cache.update(self.get_group_permissions(user_obj))
        return user_obj._perm_cache

    def has_perm(self, user_obj, perm):
        return perm in [u"%s.%s" % (p.content_type.app_label, p.codename)
                        for p in user_obj.user_permissions] or \
               perm in self.get_group_permissions(user_obj)

    def has_module_perms(self, user_obj, app_label):
        for perm in self.get_all_permissions(user_obj): 
            if perm[:perm.index('.')] == app_label: 
                return True 
        return False 

    def get_user(self, user_id):
        return User.get(user_id)
