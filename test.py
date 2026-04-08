from dotenv import dotenv_values

for key, value in dotenv_values(".env").items():
    print(f"{key}={value[:50]}{'...' if value and len(value) > 50 else ''}")