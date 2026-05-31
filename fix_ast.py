import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('202.10.46.225', username='root', password='9XqWKT!6%Z3S2r', timeout=15)

content = open('/opt/gitpup/agent.py').read()
if 'import ast' not in content:
    content = 'import ast\n' + content
    open('/opt/gitpup/agent.py', 'w').write(content)
    print('Added import ast')
else:
    print('import ast exists')

# Compile check
import py_compile
try:
    py_compile.compile('/opt/gitpup/agent.py', doraise=True)
    print('Local syntax OK')
except Exception as e:
    print('Syntax Error:', e)

ssh.close()
