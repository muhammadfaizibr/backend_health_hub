from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler for consistent error responses."""
    response = exception_handler(exc, context)

    if response is not None:
        custom_response_data = {
            'error': response.data.get('detail', str(exc)),
            'code': getattr(exc, 'code', 'error'),
        }
        if 'non_field_errors' in response.data:
            custom_response_data['error'] = response.data['non_field_errors'][0]
        response.data = custom_response_data
        response.status_code = status.HTTP_400_BAD_REQUEST if 'ValidationError' in str(type(exc)) else response.status_code

    return response