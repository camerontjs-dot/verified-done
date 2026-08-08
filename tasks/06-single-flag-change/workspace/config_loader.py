import settings


def load():
    return {"timeout": settings.DEFAULT_TIMEOUT, "retries": settings.RETRIES}
