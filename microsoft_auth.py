from calendar_services import run_microsoft_device_login


if __name__ == "__main__":
    result = run_microsoft_device_login()
    account = result.get("id_token_claims", {}).get("preferred_username", "account")
    print(f"Microsoft calendar authorization saved for {account}.")
