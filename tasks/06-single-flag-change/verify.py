import settings

assert settings.DEFAULT_TIMEOUT == 60, settings.DEFAULT_TIMEOUT
assert settings.RETRIES == 3
print("ok")
