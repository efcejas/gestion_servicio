from storages.backends.s3boto3 import S3Boto3Storage


class PrivatePortfolioStorage(S3Boto3Storage):
    """Almacenamiento privado para evidencias curriculares."""

    default_acl = 'private'
    file_overwrite = False
    querystring_auth = True
