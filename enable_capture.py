import boto3
 
sm = boto3.client('sagemaker')
 
# Get current endpoint config name
endpoint = sm.describe_endpoint(EndpointName='support-ticket-triage-2026-03-20-16-45-51-515')
current_config = endpoint['EndpointConfigName']
print(f'Current config: {current_config}')
 
# Get the existing config details
config = sm.describe_endpoint_config(EndpointConfigName=current_config)
variant = config['ProductionVariants'][0]
 
new_config_name = 'support-ticket-config-with-capture'
 
sm.create_endpoint_config(
    EndpointConfigName=new_config_name,
    ProductionVariants=[variant],
    DataCaptureConfig={
        'EnableCapture': True,
        'InitialSamplingPercentage': 100,
        'DestinationS3Uri': 's3://support-ticket-ml-build-3.17/data-capture',
        'CaptureOptions': [
            {'CaptureMode': 'Input'},
            {'CaptureMode': 'Output'}
        ],
        'CaptureContentTypeHeader': {
            'CsvContentTypes': ['text/csv'],
            'JsonContentTypes': ['application/json']
        }
    }
)
 
sm.update_endpoint(
    EndpointName='support-ticket-triage-2026-03-20-16-45-51-515',
    EndpointConfigName=new_config_name
)
 
print('Data capture enabled. Endpoint updating...')
