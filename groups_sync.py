"""
Tool to sync users from UW Groups to local system groups.
"""

import sys
import os
import yaml
import requests
import subprocess
import re


def get_uw_group_members(
    gws_base_url: str,
    gws_ca_cert: str,
    gws_client_cert: str,
    gws_client_key: str,
    uw_group: str,
) -> list:
    """
    Get UW group membership list from Groups Web Service.
    """

    r = requests.get(
        gws_base_url + "/group/" + uw_group + "/member",
        verify=gws_ca_cert,
        cert=(gws_client_cert, gws_client_key),
    )

    group_members = []

    for member in r.json()["data"]:
        if member["type"] == "uwnetid":
            # Verify personal NetID
            # https://wiki.cac.washington.edu/pages/viewpage.action?spaceKey=infra&title=UW+NetID+Namespace
            if re.match("^[a-z][a-z0-9]{0,7}$", member["id"]):
                group_members.append(member["id"])

    return group_members


def get_local_group_members(local_group: str) -> list:
    """
    Get local group membership via NSS.
    """

    r = subprocess.run(["getent", "group", local_group], capture_output=True, text=True)
    members = r.stdout.strip().split(":")[3].split(",")
    return members


def add_local_group_member(local_group: str, member: str) -> bool:
    """
    Add member to local group via gpasswd.
    """

    r = subprocess.run(
        ["gpasswd", "-a", member, local_group], capture_output=True, text=True
    )

    if r.returncode == 0:
        return True
    else:
        raise Exception(r.stderr)


def remove_local_group_member(local_group: str, member: str) -> bool:
    """
    Remove member from local group via gpasswd.
    """

    r = subprocess.run(
        ["gpasswd", "-d", member, local_group], capture_output=True, text=True
    )

    if r.returncode == 0:
        return True
    else:
        raise Exception(r.stderr)


def main():
    conf_path = os.path.dirname(os.path.abspath(__file__)) + r"/conf/groups_sync.yml"
    config = yaml.load(open(conf_path, "r"), Loader=yaml.SafeLoader)

    # Group Web Service base URL
    # Use API v3, https://wiki.cac.washington.edu/display/infra/Groups+Service+API+v3
    gws_base_url = config["gws_base_url"]
    # GWS requires certificate based auth
    gws_ca_cert = config["gws_ca_cert"]
    gws_client_cert = config["gws_client_cert"]
    gws_client_key = config["gws_client_key"]
    # key (Uw group) = value (local group)
    group_map = config["group_map"]

    for uw_group, local_group in group_map.items():
        add_count = 0
        remove_count = 0

        try:
            uw_group_member_list = get_uw_group_members(
                gws_base_url, gws_ca_cert, gws_client_cert, gws_client_key, uw_group
            )
            local_group_member_list = get_local_group_members(local_group)
        except Exception:
            print("FATAL: Error retrieving group members?", sys.exc_info())
            sys.exit(1)

        if set(uw_group_member_list) != set(local_group_member_list):
            for member in uw_group_member_list:
                if member not in local_group_member_list:
                    try:
                        add_local_group_member(local_group, member)
                        add_count += 1
                    except Exception:
                        print(
                            "ERROR: Adding {0} to {1}?".format(member, local_group),
                            sys.exc_info(),
                        )

            for member in local_group_member_list:
                if member not in uw_group_member_list:
                    try:
                        remove_local_group_member(local_group, member)
                        remove_count += 1
                    except Exception:
                        print(
                            "ERROR: Removing {0} from {1}?".format(member, local_group),
                            sys.exc_info(),
                        )
        print(
            "UWGROUP: {} LGROUP: {} ADD: {} REM: {}".format(
                uw_group, local_group, add_count, remove_count
            )
        )

    return


if __name__ == "__main__":
    main()
