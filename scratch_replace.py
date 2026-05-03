import os

filepath = 'c:/Users/Safouaine Zouaoui/Documents/pfe-monitoring-predictif-datacenter/data/Talend_datawarehouse/process/dw_pfe_0.1.item'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

tmap2_idx = content.rfind('<node componentName="tMap"')
chunk = content[tmap2_idx:]

replacements = {
    'Numeric.sequence("time", 1, 1)': 'Numeric.sequence("time2", 1, 1)',
    'Numeric.sequence("s_env", 1, 1)': 'Numeric.sequence("s_env2", 1, 1)',
    'Numeric.sequence("s_rack", 1, 1)': 'Numeric.sequence("s_rack2", 1, 1)',
    'Numeric.sequence("s_power", 1, 1)': 'Numeric.sequence("s_power2", 1, 1)',
    'Numeric.sequence("s_alert", 1, 1)': 'Numeric.sequence("s_alert2", 1, 1)'
}

for old, new in replacements.items():
    chunk = chunk.replace(old, new)

content = content[:tmap2_idx] + chunk

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replacement successful")
