"""Resume las reglas de entrada de un grupo de seguridad (JSON de describe-security-groups por stdin)."""

import json
import subprocess
import sys

names: dict[str, str] = {}


def group_name(group_id: str) -> str:
    if group_id not in names:
        names[group_id] = subprocess.run(
            ["aws", "ec2", "describe-security-groups", "--group-ids", group_id,
             "--query", "SecurityGroups[0].GroupName", "--output", "text"],
            capture_output=True, text=True, check=True).stdout.strip()
    return names[group_id]


for rule in sorted(json.load(sys.stdin), key=lambda rule: rule["FromPort"]):
    ports = str(rule["FromPort"]) if rule["FromPort"] == rule["ToPort"] else f"{rule['FromPort']}-{rule['ToPort']}"
    sources = [group_name(pair["GroupId"]) for pair in rule["UserIdGroupPairs"]] + [r["CidrIp"] for r in rule["IpRanges"]]
    print(f"    {ports}/tcp desde {', '.join(sources)}")
