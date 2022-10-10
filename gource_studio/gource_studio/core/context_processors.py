from django.conf import settings

def app_request_default(request):
    # (nav_page, label, url, logged_id)
    NAVIGATION_OPTIONS = [
        ('new', 'New Project', '/new/', True),
        ('projects', 'Projects', '/projects/', False),
        ('queue', 'Queue', '/queue/', False),
        ('avatars', 'Avatars', '/avatars/', False),
        ('playlists', 'Playlists', '/playlists/', True),
#        ('about', 'About', '/about/', False),
    ]
    # Filter some nav options for anonymous users
    if not request.user or request.user.is_anonymous:
        NAVIGATION_OPTIONS = [nav for nav in NAVIGATION_OPTIONS if not nav[3]]

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
        },
        'request_user': request.user,
    }
