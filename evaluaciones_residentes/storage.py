from storages.backends.s3boto3 import S3Boto3Storage


class EvaluacionesMediaStorage(S3Boto3Storage):
    location = 'evaluaciones_residentes'
    default_acl = 'private'
