import signal
from uuid import UUID
import cv2
import asyncio
import websockets
import json
import base64
import numpy

class ClientData:
    isLeftSide = False
    base64Image = ""

class DataSemaforo:
    estadoSemaforo1 = False
    estadoSemaforo2 = True
    prioridadeSemaforo1 = 0.5
    tempoSemaforoMax = 30
    tempoSemaforoAmarelo = 3

car_cascade = cv2.CascadeClassifier('haarcascade_cars.xml')

connected = set[websockets.WebSocketServerProtocol]()

semaforos = dict[UUID, DataSemaforo]()


async def handler(websocket:websockets.WebSocketServerProtocol):
    # Register.
    print("A client just connected")
    connected.add(websocket)
    semaforos[websocket.id] = DataSemaforo()
    try:
        consumer_task = asyncio.create_task(consumer_handler(websocket))
        producer_task = asyncio.create_task(producer_handler(websocket))
        _done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except websockets.exceptions.ConnectionClosed as _e:
        print("A client just disconnected")
    finally:
        # Unregister
        semaforos.pop(websocket.id)
        connected.remove(websocket)

async def consumer_handler(websocket:websockets.WebSocketServerProtocol):
    while True:
        async for message in websocket:
            await consumer(message, websocket.id)

async def producer_handler(websocket:websockets.WebSocketServerProtocol):
    while True:
        _message = await producer(websocket.id)
        #await websocket.send(message)

async def consumer(message:websockets.Data, socketId:UUID):
    messageString = str(message)[2:-1].replace("'",'"')
    if "Ping" in messageString:
        return
    try:
        decodedMessage = json.loads(messageString)
        print("Recebeu nova foto da camera " + ("esquerda" if decodedMessage["isLeftSide"] else "direita")  )
        image = readb64(decodedMessage["base64Image"])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cars = car_cascade.detectMultiScale(gray, 1.1, 3)
        for (x,y,w,h) in cars:
            cv2.rectangle(image,(x,y),(x+w,y+h),(0,255,0),2)
        cv2.imshow("image",image)
        cv2.waitKey(20)
        print("Tem " + str(len(cars)) + " carros na foto")
    except error:
        print("Exception e " + str(error))
    

async def producer(socketId:UUID):
    message = "Hello, World!"
    await asyncio.sleep(5) # sleep for 5 seconds before returning message
    return message

def readb64(encoded_data:str):
   nparr = numpy.frombuffer(base64.b64decode(encoded_data), numpy.uint8)
   img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
   return img

start_server = websockets.serve(handler, "localhost", 8001)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()