from django.conf import settings

def app_request_default(request):
    NAVIGATION_OPTIONS = [
        ('new', 'New Project', '/new/'),
        ('projects', 'Projects', '/projects/'),
        ('queue', 'Queue', '/queue/'),
        ('about', 'About', '/about/'),
    ]
    # Remove 'New Project' option for anonymous users
    if not request.user or request.user.is_anonymous:
        NAVIGATION_OPTIONS.pop(0)

    return {
        # Public site name
        'site_name': settings.SITE_NAME,
        # HTML document title
        'document_title': '',
        # Header navigation defaults
        'nav_options': NAVIGATION_OPTIONS,
        # Current navigation option highlighted
        'nav_page': '',
        # Shortcut to modify default padding-top on body
        'body_min_padding': False,
        # Default properties to be overloaded in suitable views
        'project_permissions': {
            'role': None,
            'view': False,
            'edit': False,
            'delete': False,
        }
    }
