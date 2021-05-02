from django.conf import settings

def app_request_default(request):
    return {
        # Public site name
        'site_name': settings.SITE_NAME,
        # HTML document title
        'document_title': '',
        # Header navigation defaults
        'nav_options': [
            ('new', 'New Project', '/new/'),
            ('projects', 'Projects', '/projects/'),
            ('queue', 'Queue', '/queue/'),
            ('about', 'About', '/about/'),
        ],
        # Current navigation option highlighted
        'nav_page': '',
        # Shortcut to modify default padding-top on body
        'body_min_padding': False,
    }
