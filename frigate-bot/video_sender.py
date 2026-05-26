import json,time,os,subprocess,urllib.request

FU='http://127.0.0.1:5000'
BT='8578914646:AAHuNQYZjxY_HjSL9oaigtLpJhwZzt4MBek'
CI='246735968'
TA='https://api.telegram.org/bot'+BT
SENT_FILE='/opt/frigate-bot/sent_events.txt'

def get_sent():
    try:
        with open(SENT_FILE) as f:return set(f.read().split())
    except:return set()

def save_sent(s):
    with open(SENT_FILE,'w') as f:f.write(chr(10).join(list(s)[-200:]))

def check():
    sent=get_sent()
    try:
        with urllib.request.urlopen(FU+'/api/events?limit=20&has_clip=1',timeout=10) as r:
            events=json.loads(r.read())
    except:return
    # Filter unsent completed person events
    candidates=[]
    for ev in events:
        eid=ev.get('id','')
        if eid in sent:continue
        if ev.get('label')!='person':continue
        if not ev.get('has_clip'):continue
        if ev.get('end_time') is None:continue
        if time.time()-(ev.get('end_time',0) or 0) < 10:continue
        # Skip events older than 1 hour (prevent resending old alerts)
        if time.time()-(ev.get('start_time',0) or 0) > 3600:
            sent.add(eid)
            save_sent(sent)
            continue
        duration=(ev.get('end_time',0) or 0)-(ev.get('start_time',0) or 0)
        if duration < 3:
            sent.add(eid)
            save_sent(sent)
            continue
        score=ev.get('top_score') or ev.get('data',{}).get('top_score') or 1
        if score < 0.6:
            sent.add(eid)
            save_sent(sent)
            continue
        candidates.append(ev)
    if not candidates:return
    # Group by overlapping time (within 30 sec = same group)
    candidates.sort(key=lambda x:x.get('start_time',0))
    groups=[]
    current_group=[candidates[0]]
    for ev in candidates[1:]:
        if ev.get('start_time',0)-(current_group[-1].get('end_time',0) or 0) < 30:
            current_group.append(ev)
        else:
            groups.append(current_group)
            current_group=[ev]
    groups.append(current_group)
    # Send only longest clip from each group
    for group in groups:
        best=max(group,key=lambda x:(x.get('end_time',0) or 0)-(x.get('start_time',0) or 0))
        eid=best.get('id')
        try:
            clip_url=FU+'/api/events/'+eid+'/clip.mp4'
            with urllib.request.urlopen(clip_url,timeout=60) as r:
                clip=r.read()
            if len(clip)>10000:
                with open('/tmp/event_clip.mp4','wb') as f:f.write(clip)
                subprocess.run(['curl','-s','-F','chat_id='+CI,'-F','video=@/tmp/event_clip.mp4','-F','caption=\u203c\ufe0f\U0001f4f8 \u0414\u0432\u0438\u0436\u0435\u043d\u0438\u0435 \u0432 \u043f\u043e\u0434\u044a\u0435\u0437\u0434\u0435 \U0001f4f8\u203c\ufe0f',TA+'/sendVideo'],capture_output=True,timeout=120)
                os.remove('/tmp/event_clip.mp4')
                print('Sent',eid[:8])
        except Exception as e:
            print('Error:',e)
        for ev in group:
            sent.add(ev.get('id',''))
        save_sent(sent)

print('Video sender v5 (clips) started')
while True:
    check()
    time.sleep(10)
