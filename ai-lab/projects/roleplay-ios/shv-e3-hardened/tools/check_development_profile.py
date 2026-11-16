#!/usr/bin/env python3
"""Preflight decoded Apple Development profile and requested entitlements.
Only consistency; does not attest to code-signing identity, install or device.
"""
import argparse,json,plistlib,re,sys
from datetime import datetime,timezone
from pathlib import Path
class ProfileError(ValueError):pass

def check(profile,requested,*,bundle_id="com.macport.gtav",device_udid=None,now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ProfileError("invalid clock")
    ent=profile.get("Entitlements")
    if not isinstance(ent,dict):raise ProfileError("missing profile entitlements")
    teams=profile.get("TeamIdentifier")
    if not isinstance(teams,list) or len(teams)!=1 or not re.fullmatch("[A-Z0-9]{10}",str(teams[0])):
        raise ProfileError("unknown/multiple TeamIdentifier")
    team=teams[0];app=team+"."+bundle_id
    if ent.get("application-identifier")!=app:
        raise ProfileError("profile does not authorize exact app identifier")
    if ent.get("com.apple.developer.team-identifier")!=team:
        raise ProfileError("profile team mismatch")
    if ent.get("get-task-allow") is not True:
        raise ProfileError("not a development/debuggable profile")
    expiry=profile.get("ExpirationDate")
    if not isinstance(expiry,datetime):raise ProfileError("profile has no expiry")
    if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=timezone.utc)
    if expiry<=now:raise ProfileError("profile expired")
    devices=profile.get("ProvisionedDevices")
    if not isinstance(devices,list) or not devices:raise ProfileError("profile has no test devices")
    if device_udid and device_udid not in devices:raise ProfileError("device not provisioned")
    if requested.get("application-identifier")!=app:raise ProfileError("requested app ID mismatch")
    if requested.get("com.apple.developer.team-identifier")!=team:
        raise ProfileError("requested team mismatch")
    if requested.get("get-task-allow") is not True:
        raise ProfileError("requested entitlements lack debugger access")
    for key,val in requested.items():
        if key not in ent:raise ProfileError("entitlement not in profile: "+str(key))
        permitted=ent[key]
        if isinstance(val,list) and isinstance(permitted,list):
            if any(x not in permitted for x in val):raise ProfileError("entitlement value mismatch: "+str(key))
        elif val!=permitted:raise ProfileError("entitlement value mismatch: "+str(key))
    return {"status":"PROFILE_ENTITLEMENTS_CONSISTENT","bundle_id":bundle_id,
      "team_id":team,"device_membership_checked":device_udid is not None,
      "certificate_matches_profile_verified":False,
      "signed_application_or_install_verified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--decoded-profile",type=Path,required=True)
    p.add_argument("--entitlements",type=Path,required=True)
    p.add_argument("--device-udid")
    a=p.parse_args()
    try:
        with a.decoded_profile.open("rb") as f:profile=plistlib.load(f)
        with a.entitlements.open("rb") as f:entitlements=plistlib.load(f)
        out=check(profile,entitlements,device_udid=a.device_udid);rc=0
    except (OSError,ValueError,TypeError,plistlib.InvalidFileException) as e:
        out={"status":"REJECTED","reason":str(e)};rc=2
    print(json.dumps(out,sort_keys=True))
    return rc
if __name__=="__main__":sys.exit(main())
