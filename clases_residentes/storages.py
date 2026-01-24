from storages.backends.s3boto3 import S3Boto3Storage

class S3MediaStorage(S3Boto3Storage):
    location = 'clases_residentes'  # Carpeta lógica dentro del bucket
    default_acl = 'private'  # Cambia a 'public-read' si quieres acceso público
