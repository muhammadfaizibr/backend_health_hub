from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler for consistent error responses."""
    response = exception_handler(exc, context)

    if response is not None:
        # Handle validation errors (field-specific errors)
        if isinstance(response.data, dict) and any(
            key not in ['detail', 'code'] for key in response.data.keys()
        ):
            # This is a validation error with field-specific errors
            custom_response_data = {
                'errors': response.data,
                'code': 'validation_error',
            }
        # Handle non-field errors
        elif 'non_field_errors' in response.data:
            custom_response_data = {
                'error': response.data['non_field_errors'][0] if isinstance(
                    response.data['non_field_errors'], list
                ) else response.data['non_field_errors'],
                'code': getattr(exc, 'code', 'error'),
            }
        # Handle detail errors (like authentication errors)
        elif 'detail' in response.data:
            custom_response_data = {
                'error': response.data['detail'],
                'code': getattr(exc, 'code', 'error'),
            }
        # Fallback for other error types
        else:
            custom_response_data = {
                'error': str(exc),
                'code': getattr(exc, 'code', 'error'),
            }
        
        response.data = custom_response_data

    return response 