"""Menu content and validated native commands shared by the bubble UI."""
import json,random

def random_variant(catalog,current):
    others=[entry for entry in catalog if not current or entry['petId']!=current['petId']]
    candidates=others or [entry for entry in catalog if not current or entry['id']!=current['id']]
    if not candidates:return None
    pet=random.choice(list(dict.fromkeys(entry['petId'] for entry in candidates)))
    return random.choice([entry for entry in candidates if entry['petId']==pet])

def menu_items(desktop):
    clips=set(desktop.variant['clips']);petting={'Sequence_Pet_In','Sequence_Pet_Loop','Sequence_Pet_Out'}<=clips
    actions=[('greet','问候','Emote_Greetings'),('pet','抚摸',None),('happy','开心','Reaction_Happy_Big'),('wow','惊叹','Emote_Wow'),('threaten','威胁','Emote_Threaten'),('flight','起飞！','Sequence_Flying_Idle') if 'Sequence_Flying_Idle' in clips else ('idle-happy','挂机','Idle_Happy')]
    emotions=[{'id':key,'label':label,'enabled':petting if key=='pet' else clip in clips} for key,label,clip in actions]
    controls=[('lock','解锁视角' if desktop.view_locked else '锁定视角',True),('reset','恢复视角',not desktop.view_locked),('sound','开启声音' if desktop.muted else '关闭声音',bool(desktop.variant.get('sounds'))),('random','换一个',bool(getattr(desktop,'random_pet',None))),('panel','管理面板',bool(desktop.open_panel)),('quit','退出',True)]
    return {'emotions':emotions,'controls':[{'id':key,'label':label,'enabled':enabled} for key,label,enabled in controls]}

def perform_menu_action(desktop,key):
    items=menu_items(desktop)
    if not any(item['id']==key and item['enabled'] for row in items.values() for item in row):return
    commands={'greet':'Emote_Greetings','pet':'pet','happy':'Reaction_Happy_Big','wow':'Emote_Wow','threaten':'Emote_Threaten','idle-happy':'Idle_Happy'}
    if key in commands:desktop.view.page().runJavaScript('petCommand('+json.dumps(commands[key])+')')
    elif key=='flight':desktop.view.page().runJavaScript('petCommand(window.petState==="Sequence_Flying_Idle"?"Idle_Neutral":"Sequence_Flying_Idle")')
    elif key=='lock':desktop.set_view_locked(not desktop.view_locked)
    elif key=='reset':desktop.view.page().runJavaScript('petResetView()')
    elif key=='sound':desktop.toggle_sound()
    elif key=='panel':desktop.open_panel()
    elif key=='quit':desktop.quit()
    elif key=='random':desktop.random_pet()
