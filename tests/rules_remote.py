"""Run the proposed rules in Firebase's test API; OAuth stays in process memory."""
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = '/databases/(default)/documents/'
LIVE = BASE + 'atlas_operator_live_v1/current'
OWNER = {'uid':'synthetic-owner','token':{'email':'mithunkurian@gmail.com','email_verified':True,
         'firebase':{'sign_in_provider':'google.com'}}}
RELAY = {'uid':'atlas-portal-relay-v1','token':{'atlas_relay':True,
         'firebase':{'sign_in_provider':'custom'}}}


def cases():
    result=[]
    def add(allow,method,auth,path=LIVE,data=None):
        request={'path':path,'method':method,'auth':auth}
        if data is not None: request['resource']={'data':data}
        result.append({'expectation':'ALLOW' if allow else 'DENY','request':request,
                       'resource':{'data':{'schema':1,'payload':'{}'}}})
    add(True,'get',OWNER)
    add(False,'get',None)
    add(False,'get',{'uid':'other','token':OWNER['token']|{'email':'other@example.com'}})
    add(False,'get',{'uid':'other','token':OWNER['token']|{'email_verified':False}})
    add(False,'get',{'uid':'other','token':OWNER['token']|{'firebase':{'sign_in_provider':'custom'}}})
    for auth in (OWNER,RELAY,None):
        for method in ('list','delete'):
            add(False,method,auth)
        for path in ('historical/private','atlas_operator_requests_v1/resume','atlas_operator_live_v1/other'):
            add(False,'get',auth,BASE+path)
            add(False,'create',auth,BASE+path,{'schema':1,'payload':'{}'})
    add(False,'get',RELAY)
    for method in ('create','update'):
        add(True,method,RELAY,data={'schema':1,'payload':'{}'})
        add(False,method,OWNER,data={'schema':1,'payload':'{}'})
        add(False,method,None,data={'schema':1,'payload':'{}'})
        add(False,method,RELAY,data={'schema':1,'payload':'{}','extra':True})
        add(False,method,RELAY,data={'schema':2,'payload':'{}'})
        add(False,method,RELAY,data={'schema':1,'payload':123})
        add(False,method,RELAY,data={'schema':1,'payload':'x'*131073})
    return result


def main():
    token=subprocess.check_output([shutil.which('gcloud.cmd') or 'gcloud','auth','print-access-token'],
                                  text=True,stderr=subprocess.PIPE).strip()
    tests=cases()
    payload={'source':{'files':[{'name':'firestore.rules','content':(ROOT/'firestore.rules').read_text()}]},
             'testSuite':{'testCases':tests}}
    request=urllib.request.Request('https://firebaserules.googleapis.com/v1/projects/portalnexy:test',
        data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json',
                                                  'x-goog-user-project':'portalnexy'})
    with urllib.request.urlopen(request,timeout=60) as response: result=json.load(response)
    issues=[item for item in result.get('issues',[]) if item.get('severity')=='ERROR']
    failures=[(i,item.get('state'),item.get('errors')) for i,item in enumerate(result.get('testResults',[]))
              if item.get('state')!='SUCCESS']
    if issues or failures or len(result.get('testResults',[]))!=len(tests):
        raise SystemExit(json.dumps({'issues':issues,'failures':failures,'results':len(result.get('testResults',[]))}))
    print(f'Firebase remote rules: {len(tests)} allow/deny cases passed; no rules deployed or database writes.')


if __name__=='__main__': main()
