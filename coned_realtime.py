import requests
import jwt
import pyttsx3
import datetime
import pytz
import time

def send_sms_ifttt(msg):
    payload = { "message" : msg } #optional
    resp = requests.post(f'https://maker.ifttt.com/trigger/{ifttt_event_name}/json/with/key/{ifttt_key}', data=payload)
    #print(resp.text)
def speak_text(txt):
    engine = pyttsx3.init()
    engine.say(txt)
    engine.setProperty('volume', 1.0)
    engine.runAndWait()
    engine.stop()


def need_new_token(jwt_token: str):
    try:
        resp=jwt.decode(jwt_token, options={"verify_signature": False}, algorithms=["RS256"])
        expired_epoch = resp.get('exp', 0)
        current_epoch = int(datetime.datetime.now().timestamp())
        diff = expired_epoch - current_epoch
        if diff > 120:
            return False
        else:
            return True
    except(jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return True



def get_token():
    login_url = login_base_url + "/Login"
    payload = {
        "LoginEmail": username,
        "LoginPassword": password,
        "LoginRememberMe": False,
        "ReturnUrl": return_url,
        "OpenIdRelayState": "",
    }

    sess = requests.session()

    if use_ce_device_id:
        sess.cookies.update({'CE_DEVICE_ID': ce_device_id})
        resp = sess.post(login_url, payload, headers=login_headers)
    else:
        sess.post(login_url, payload, headers=login_headers)
        payload_mfa = {
            "MFACode": mfa_secret_answer,
            "ReturnUrl": return_url,
            "OpenIdRelayState": "",
        }
        resp = sess.post(login_base_url + "/VerifyFactor", data=payload_mfa, headers=login_headers)

    login_redirect_url = resp.json().get('authRedirectUrl', "")
    sess.get(login_redirect_url, headers={"User-Agent": user_agent}, allow_redirects=True)
    login_final_url = "https://www.coned.com/sitecore/api/ssc/ConEd-Cms-Services-Controllers-Opower/OpowerService/0/GetOPowerToken"
    return sess.get(login_final_url, headers=login_headers).json()


def get_realtime_electric_usage(jwt_tkn):
    usage_electric_url = f"https://cned.opower.com/ei/edge/apis/cws-real-time-ami-v1/cws/cned/accounts/{account_uuid}/meters/{meter_id}/usage"
    reads = requests.get(usage_electric_url, headers={'Authorization': f'Bearer {jwt_tkn}'}).json().get('reads', [])
    reads.reverse()
    for read in reads:
        value = read.get('value')
        start_datetime_str = read.get('startTime')
        end_datetime_str = read.get('endTime')
        start_time = datetime.datetime.fromisoformat(start_datetime_str).strftime("%I:%M %p")
        end_time = datetime.datetime.fromisoformat(end_datetime_str).strftime("%I:%M %p")
        hash_obj = start_datetime_str + end_datetime_str + str(value)
        end_date = datetime.datetime.fromisoformat(end_datetime_str).strftime("%b %d") #%b %d %Y

        if value and value >= max_trigger_value and hash_obj not in list_of_prior_alerts:
            alert_text = f"ALERT: USAGE is {round(value, 1)} KWH between {end_date} {start_time} and {end_time}"
            print(alert_text)
            speak_text(alert_text)
            send_sms_ifttt(alert_text)
            list_of_prior_alerts.append(hash_obj)





if __name__ == "__main__":

    """
    For MFA Security Question, to set up your MFA secret (answer), log into coned.com, 
    go to your profile and reset your 2FA method. 
    When setting up 2FA again, there will be option to say you do not have texting on your phone. 
    Select this and you should be able to use a security question instead.
    
    
    For account uuid, log into coned.com then use the browser developer tools to search 
    for a GET request to opower.com with the word utilityAccounts that 
    looks like: https://cned.opower.com/ei/edge/apis/DataBrowser-v1/cws/utilities/cned/utilityAccounts/
    ACCOUNT_UUID/reads?aggregateType=bill&includeEnhancedBilling=false&includeMultiRegisterData=false
    
    use_ce_device_id can be used to bypass the login process by providing a CE Device ID
    
    
    """
    
    username = "myemail@email.com"
    password = ""
    use_ce_device_id = True
    mfa_secret_answer = ""
    ce_device_id = ''
    login_base_url = "https://www.coned.com/sitecore/api/ssc/ConEdWeb-Foundation-Login-Areas-LoginAPI/User/0"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    return_url = "/en/accounts-billing/my-account/energy-use"
    login_headers = {
        "User-Agent": user_agent,
        "Referer": "https://www.coned.com/",
    }

    # realtime usage
    meter_id = ''
    account_uuid = ''
    max_trigger_value = 1  # 1KWH
    scan_interval = 900
    ifttt_key = ''
    ifttt_event_name = "electric_usage_alert"
    jwt_token = ""
    list_of_prior_alerts = []
    while True:
        print(f"TIME is {datetime.datetime.now()}")
        if need_new_token(jwt_token):
            jwt_token = get_token()
            print(f'Getting new token {jwt_token}')
        else:
            print(f"Using existing jwt token {jwt_token}")

        get_realtime_electric_usage(jwt_token)
        time.sleep(scan_interval)
