#!/usr/bin/env python3
import os,json,time,subprocess,urllib.request,glob
from datetime import datetime
BT='8578914646:AAHuNQYZjxY_HjSL9oaigtLpJhwZzt4MBek'
CI='246735968'
FU='http://127.0.0.1:5000'
CR='rtsp://admin:Padsxy29zt@192.168.0.113:554/cam/realmonitor?channel=1&subtype=0'
TA='https://api.telegram.org/bot'+BT
def tg(method,data=None,files=None):
    url=TA+'/'+method
    if files:
        bd='---Bound7'
        body=b''
        for k,v in(data or{}).items():body+=('--'+bd+'\rContent-Disposition: form-data; name="'+k+'"\r\r'+str(v)+'\r').encode()
        for k,(fn,fd,ct) in files.items():
            body+=('--'+bd+'\rContent-Disposition: form-data; name="'+k+'"; filename="'+fn+'"\rContent-Type: '+ct+'\r\r').encode()
            body+=fd+b'\r'
        body+=('--'+bd+'--\r').encode()
        req=urllib.request.Request(url,data=body);req.add_header('Content-Type','multipart/form-data; boundary='+bd)
    else:
        body=json.dumps(data or{}).encode();req=urllib.request.Request(url,data=body);req.add_header('Content-Type','application/json')
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read())
    except:return None
def msg(text,kb2=None):
    import subprocess as sp2
    d={'chat_id':CI,'text':text}
    if kb2:d['reply_markup']=json.dumps(kb2)
    body=json.dumps(d).encode()
    req=urllib.request.Request(TA+'/sendMessage',data=body)
    req.add_header('Content-Type','application/json')
    urllib.request.urlopen(req,timeout=10)

def kb():
    return{'keyboard':[[{'text':'Снимок'},{'text':'Запись видео'}],[{'text':'Статус Frigate'},{'text':'Статус сервера'}]],'resize_keyboard':True}
def fapi(ep):
    try:
        with urllib.request.urlopen(FU+'/api/'+ep,timeout=10) as r:return json.loads(r.read())
    except Exception as e:return{'error':str(e)}
def do_status():
    s=fapi('stats')
    if 'error' in s:
        return 'Frigate не отвечает'
    u=s.get('service',{}).get('uptime',0)
    h=int(u//3600);m=int((u%3600)//60)
    ci='';di=''
    for n,d in s.get('cameras',{}).items():
        ci=str(d.get('camera_fps',0))+' fps'
    for n,d in s.get('detectors',{}).items():
        di=str(int(d.get('inference_speed',0)))+'ms'
    try:
        r=subprocess.run(['docker','stats','--no-stream','--format','{{.Name}}|{{.CPUPerc}}'],capture_output=True,text=True,timeout=10)
        cpu='?'
        for l in r.stdout.strip().split(chr(10)):
            if 'frigate' in l and 'notify' not in l:
                cpu=l.split('|')[1] if '|' in l else '?'
    except:
        cpu='?'
    try:
        r2=subprocess.run(['du','-sh','/opt/frigate/storage/'],capture_output=True,text=True,timeout=10)
        disk=r2.stdout.split()[0] if r2.stdout else '?'
    except:
        disk='?'
    try:
        ev=fapi('events?limit=100&after='+str(int(time.time())-86400))
        today=str(len([e for e in ev if e.get('label')=='person'])) if isinstance(ev,list) else '0'
    except:
        today='0'
    t = chr(9989)+" Frigate работает"
    t += chr(10)+chr(10)+chr(9201)+" Аптайм: "+str(h)+"ч "+str(m)+"мин"
    t += chr(10)+chr(128247)+" Камера: "+ci
    t += chr(10)+chr(129504)+" AI: "+di+"/кадр"
    t += chr(10)+chr(128187)+" CPU: "+cpu
    t += chr(10)+chr(128193)+" Записей: "+disk
    t += chr(10)+chr(128100)+" Событий: "+today
    return t
def do_snap():
    try:
        subprocess.run(['ffmpeg','-rtsp_transport','tcp','-i',CR,'-frames:v','1','-q:v','2','/tmp/snap.jpg','-y'],capture_output=True,timeout=10);img=None
        pass
        subprocess.run(['curl','-s','-F','chat_id='+CI,'-F','photo=@/tmp/snap.jpg','-F','caption=\u203c\ufe0f\U0001f4f8 Снимок с камеры \U0001f4f8\u203c\ufe0f',TA+'/sendPhoto'],capture_output=True,timeout=15)
        os.remove('/tmp/snap.jpg')
    except Exception as e:msg('Err: '+str(e))
def do_record():
    fp='/tmp/br.mp4'
    try:
        subprocess.run(['ffmpeg','-rtsp_transport','tcp','-i',CR,'-t','5','-c:v','copy','-an',fp,'-y'],capture_output=True,timeout=30)
        subprocess.run(['curl','-s','-F','chat_id='+CI,'-F','video=@'+fp,'-F','caption=\u203c\ufe0f\U0001f4f8 \u0412\u0438\u0434\u0435\u043e \u0441 \u043a\u0430\u043c\u0435\u0440\u044b 5 \u0441\u0435\u043a \U0001f4f8\u203c\ufe0f',TA+'/sendVideo'],capture_output=True,timeout=60)
        os.remove(fp)
    except Exception as e:msg('Err: '+str(e))
def do_server():
    with open('/proc/meminfo') as f:
        m={}
        for l in f:
            p=l.split()
            if p[0] in('MemTotal:','MemAvailable:'):m[p[0]]=int(p[1])
    t=m.get('MemTotal:',0)/1024/1024;a=m.get('MemAvailable:',0)/1024/1024
    with open('/proc/uptime') as f:up=float(f.read().split()[0])
    h=int(up//3600);mn=int((up%3600)//60)
    r=subprocess.run(['df','-h','/'],capture_output=True,text=True)
    dl=r.stdout.strip().split(chr(10))[-1].split()
    temps=[]
    for z in sorted(glob.glob('/sys/class/thermal/thermal_zone*/temp')):
        with open(z) as f:temps.append(int(f.read().strip())//1000)
    temp=str(max(temps)) if temps else '?'
    txt=chr(128421)+' \u0421\u0442\u0430\u0442\u0443\u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u0430'
    txt+=chr(10)+chr(10)+chr(9201)+' \u0410\u043f\u0442\u0430\u0439\u043c: '+str(h)+'\u0447 '+str(mn)+'\u043c\u0438\u043d'
    txt+=chr(10)+chr(128190)+' RAM: '+str(round(t-a,1))+'/'+str(round(t,1))+' \u0413\u0411'
    txt+=chr(10)+chr(128191)+' \u0414\u0438\u0441\u043a: '+dl[2]+'/'+dl[1]+' ('+dl[4]+')'
    txt+=chr(10)+chr(127777)+' \u0422\u0435\u043c\u043f\u0435\u0440\u0430\u0442\u0443\u0440\u0430 CPU: '+temp+chr(176)+'C'
    return txt
def handle(text):
    if text=='/start':msg('\U0001f44b Frigate Bot\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435:',kb())
    elif '\u0421\u0442\u0430\u0442\u0443\u0441 Frigate' in text:
        st=do_status()
        body2=json.dumps({'chat_id':CI,'text':st}).encode()
        req2=urllib.request.Request(TA+'/sendMessage',data=body2)
        req2.add_header('Content-Type','application/json')
        urllib.request.urlopen(req2,timeout=10)
    elif '\u0421\u043d\u0438\u043c\u043e\u043a' in text:do_snap()
    elif '\u0417\u0430\u043f\u0438\u0441\u044c' in text:do_record()
    elif '\u0421\u0442\u0430\u0442\u0443\u0441 \u0441\u0435\u0440\u0432\u0435\u0440\u0430' in text:
        st2=do_server()
        body3=json.dumps({'chat_id':CI,'text':st2}).encode()
        req3=urllib.request.Request(TA+'/sendMessage',data=body3)
        req3.add_header('Content-Type','application/json')
        urllib.request.urlopen(req3,timeout=10)
    else:msg('\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u043c\u0435\u043d\u044e:',kb())
def main():
    print('Bot started')
    offset=0
    while True:
        try:
            with urllib.request.urlopen(TA+'/getUpdates?offset='+str(offset)+'&timeout=30&allowed_updates=["message"]',timeout=60) as r:data=json.loads(r.read())
            if data.get('ok') and data.get('result'):
                for u in data['result']:
                    offset=u['update_id']+1
                    m2=u.get('message',{});txt=m2.get('text','');cid=str(m2.get('chat',{}).get('id',''))
                    if cid==CI and txt:handle(txt)
        except:time.sleep(5)
if __name__=='__main__':main()
