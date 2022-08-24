import json, asyncio, os, time, logging
from functools import partial
from nio import AsyncClient, MatrixRoom, RoomMessageText
from Kronos import Kronos
cred = json.load(open('config.json'))

DRY_RUN = False
ROOM_ID = cred['room_id']
MATRIX_USER = cred['whitelist']
MATRIX_SERVER = cred['matrix_server']


async def parse_punch(client,kronos,clock_type,transfer=None,duration=0,units=None):
    print(f"Punching {clock_type} for {duration:.2f} {units}")
    await client.room_send(room_id=ROOM_ID,
                           message_type="m.room.message",
                           content={"msgtype": "m.text", "body": f"Clocking {clock_type}; please accept incoming 2FA!"})
    if clock_type=="in":
        response = kronos.clock_in(transfer)
    elif clock_type=="out":
        response = kronos.clock_out()
    if not isinstance(response,str) and clock_type == 'in':
        asyncio.create_task(future_punch_out(client,kronos,duration,units,transfer))
    return response
    
async def future_punch_out(client,kronos,duration,units,transfer):
    secconds = 0
    if 'hour' in units.lower():
        secconds = duration*60*60
    elif 'min' in units:
        secconds = duration*60
    if secconds <= 60:
        message = "ERROR: The duration is not long enough. Mannually clock out!!!"
        await client.room_send(room_id=ROOM_ID,
                               message_type="m.room.message",
                               content={"msgtype": "m.text", "body": message})
        return 
        
    await client.room_send(room_id=ROOM_ID,
                           message_type="m.room.message",
                           content={"msgtype": "m.text", "body": f"Resing for {secconds} secconds before clock-out!"})
    time.sleep(secconds-60)
    message = f"About to clock out; prepare to confirm 2FA in 60 secconds!"
    await client.room_send(room_id=ROOM_ID,
                           message_type="m.room.message",
                           content={"msgtype": "m.text", "body": message})
    time.sleep(60)
    clocked_out = False
    counter = 0
    limit = 5
    while counter <= limit and not clocked_out:
        message = "Clocking out; please accept incoming 2FA!"
        await client.room_send(room_id=ROOM_ID,
                               message_type="m.room.message",
                               content={"msgtype": "m.text", "body": message})
        
        response = kronos.clock_out()
        message = ""
        
        if isinstance(response,str):
            #error
            message = response
            counter += 1
            if counter < limit: message += "\nAttempting to clock out again!"
            elif counter == limit: message += f"\nFailed to clock out {limit}! Please clock out manully."
        else:
            #success
            clocked_out = True
            message = "Successful clock out!"
        await client.room_send(room_id=ROOM_ID,
                               message_type="m.room.message",
                               content={"msgtype": "m.text", "body": message})


#DIAGNOSTIC COMMAND
async def run_diagnostic(client,kronos, message):
    logging.info("Diagnostic command recieved")
    await send_message(client,"Fetching timesheet; incoming 2FA.")
    response = kronos.diag()
    if isinstance(response,str):
        return {'error': True, 'message': response}
    else:
        message = ""
        for row in response:
            message += '; '.join(row)+'\n'
        return {'error': False, 'message': message, 'data': response}

#DIAGNOSTIC COMMAND
async def check_idle(client,kronos, message):
    logging.info("Checking if selenium is idle")
    send_message(client,"Fetching timesheet; incoming 2FA.")
    idle = kronos.isIdle()
    if idle:
        return {'error': False, 'message': "Yes this is idle."}
    else:
        return {'error': False, 'message': "No the session is not idle."}

#PUNCH IN/OUT COMMAND
#Punch in defined by four components
async def run_punch_in(client, kronos, message, components):
    logging.info("Possible punch in command recieved")    
    clock_type,duration,units,transfer=components
    try:
        float(duration)
        int(transfer)
    except:
        #FAILED TO MAKE REQUEST
        return {'error': True, 'message': 'Bad command: Not correct order/types'}
    duration = float(duration)
    if clock_type == 'in' and ('min' in units or 'hour' in units):
        #SUCCESSFUL COMMAND PARSED
        response = await parse_punch(client,kronos,clock_type,transfer,duration,units)
        if isinstance(response,str):
            #Error with kronos/selenium
            return {'error': True, 'message': f'ERROR: {response}'}
        else:
            #Success!
            return {'error': False, 'message': f'Successfully clocked {clock_type} for {duration} {units} under transfer {transfer}!'}

#Punch out defined by two components
async def run_punch_out(client, kronos,message,components):
    logging.info("Possible punch out command recieved")        
    clock_type=components[0]
    if clock_type =='out':
        #SUCCESSFUL COMMAND PARSED
        response = await parse_punch(client,kronos,clock_type)
        if isinstance(response,str):
            #Error with kronos/selenium
            return {'error': True, 'message': response}
        else:
            #Success!
            return {'error': False, 'message': f'Successfully clocked {clock_type}!'}
    return {'error': True, 'message': f'Unknown command {components[0]}'}

#PARSE COMMAND FROM MATRIX
async def parse_arguments(client,kronos,message):
    logging.info("PARSING ARGUMENTS")
    ##single word request
    if message.lower().strip()[:4]=="diag":
        return await run_diagnostic(client,kronos,message)
    elif message.lower().strip()[:4]=="idle":
        return await check_idle(client,kronos,message)
    
    ##Clocking in/out Request
    components = [m for m in message.lower().replace('clock','').replace('  ',' ').split(' ') if m != '']
    logging.info(f"Components {str(components)}")
    if len(components) == 4:
        return await run_punch_in(client, kronos,message,components)
    elif len(components)==1:
        return await run_punch_out(client, kronos,message,components)

    ##Issue with request
    print(components)
    return {'error': True, 'message': 'Bad command: Not correct number of arguments (2/4)'}
            

async def message_callback(client,kronos, room: MatrixRoom, event: RoomMessageText) -> None:
    last_time = 0
    if os.path.isfile('last_message.txt'):
        with open('last_message.txt') as f:
            last_time = int(f.read())
    if (event.server_timestamp>last_time
        and room.display_name.lower()=="kronos"
        and event.sender.lower()==MATRIX_USER):
            with open('last_message.txt','w+') as f:
                f.write(str(event.server_timestamp))
            print(
                f"Message received in room {room.display_name}\n"
                f"{room.user_name(event.sender)} | {event.body}",
                str(event.server_timestamp)
            )
            message = event.body
            resp = await parse_arguments(client,kronos,message)
            await client.room_send(room_id=ROOM_ID,
                             message_type="m.room.message",
                             content={"msgtype": "m.text", "body": resp['message']})

async def send_message(client,message):
    return await client.room_send(room_id=ROOM_ID,
                           message_type="m.room.message",
                           content={"msgtype": "m.text", "body": message})
    
            
async def main() -> None:
    print(f"https://{MATRIX_SERVER}", f"@{cred['matrix_user']}:{MATRIX_SERVER}")
    client = AsyncClient(f"https://{MATRIX_SERVER}", f"@{cred['matrix_user']}:{MATRIX_SERVER}")
    
    kronos = Kronos(headless=True,dry_run=False,persist=True)
    kronos.login()
    with open('last_message.txt','w+') as f:
        f.write(str(int(time.time()*1000)))
    
    client.add_event_callback(partial(message_callback,client,kronos), RoomMessageText)
    print(await client.login(cred['matrix_password']))
    await send_message(client,"Kronos bot started!")
    
    await client.sync_forever(timeout=30000)  # milliseconds


asyncio.run(main())
