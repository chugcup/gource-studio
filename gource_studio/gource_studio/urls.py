from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('gource_studio.core.urls')),
    path('api/v1/', include('gource_studio.core.api.urls')),
#    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
