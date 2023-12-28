from uuid import UUID
import cv2
import asyncio
import websockets
import json
import base64
import numpy


class ReceivedData:
    isLeftSide = False
    base64Image = ""


class StoplightStatus:
    leftStoplightStatus = "Green"
    rightStoplightStatus = "Red"


averageOpenTime = 10
yellowTime = 3.0


class StoplightData:
    leftIsOpen = True
    priorityLeft = 0.5
    stayOpenTill = 20.0
    currentTime = 0.0
    carCountLeft = 0
    carCountRight = 0
    lastSentData: StoplightStatus


def readb64(encoded_data: str):
    nparr = numpy.frombuffer(base64.b64decode(encoded_data), numpy.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img


car_cascade = cv2.CascadeClassifier("haarcascade_cars.xml")

connected = set[websockets.WebSocketServerProtocol]()

stoplightDict = dict[UUID, StoplightData]()


async def handler(websocket: websockets.WebSocketServerProtocol):
    # Register.
    print("O cliente " + str(websocket.id) + " acabou de conectar")
    connected.add(websocket)
    stoplightDict[websocket.id] = StoplightData()
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
        print("O cliente " + str(websocket.id) + " acabou de desconectar")
    finally:
        # Unregister
        cv2.destroyAllWindows()
        stoplightDict.pop(websocket.id)
        connected.remove(websocket)


async def consumer_handler(websocket: websockets.WebSocketServerProtocol):
    while True:
        async for message in websocket:
            if websocket.closed:
                break
            await consumer(message, websocket.id)


async def producer_handler(websocket: websockets.WebSocketServerProtocol):
    while True:
        if websocket.closed:
            break
        message = await producer(websocket.id)
        print("Enviando mensagem " + message)
        await websocket.send(message)


async def consumer(message: websockets.Data, socketId: UUID):
    messageString = str(message)[2:-1].replace("'", '"')
    if "Ping" in messageString:
        return
    try:
        decodedMessage = json.loads(messageString)
        isLeftSide = decodedMessage["isLeftSide"]
        sideTitle = "esquerda" if isLeftSide else "direita"
        print("Recebeu nova foto da camera " + sideTitle)
        image = readb64(decodedMessage["base64Image"])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cars = car_cascade.detectMultiScale(gray, 1.1, 3)
        for x, y, w, h in cars:
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow(sideTitle + str(socketId), image)
        cv2.waitKey(20)
        carCount = len(cars)

        if isLeftSide:
            stoplightDict[socketId].carCountLeft = carCount
        else:
            stoplightDict[socketId].carCountRight = carCount

    except error:
        print("Exception e " + str(error))


async def producer(socketId: UUID):
    clientStoplight = stoplightDict[socketId]
    clientStoplight.currentTime += 1
    clientStoplight.priorityLeft = (clientStoplight.carCountLeft + 1) / (
        clientStoplight.carCountRight + 1
    )
    correctedPriority = (
        clientStoplight.priorityLeft
        if clientStoplight.leftIsOpen
        else 1 / clientStoplight.priorityLeft
    )
    clientStoplight.stayOpenTill = averageOpenTime * correctedPriority

    stoplightStatus = StoplightStatus()

    if clientStoplight.currentTime > clientStoplight.stayOpenTill:
        if (
            clientStoplight.leftIsOpen == True
            and clientStoplight.lastSentData.leftStoplightStatus == "Green"
        ):
            stoplightStatus.leftStoplightStatus = "Yellow"
            clientStoplight.currentTime -= yellowTime

        elif (
            clientStoplight.leftIsOpen == False
            and clientStoplight.lastSentData.rightStoplightStatus == "Green"
        ):
            stoplightStatus.rightStoplightStatus = "Yellow"
            clientStoplight.currentTime -= yellowTime

        elif clientStoplight.leftIsOpen == True:
            stoplightStatus.rightStoplightStatus = "Green"
            stoplightStatus.leftStoplightStatus = "Red"
            clientStoplight.leftIsOpen = False

        else:
            stoplightStatus.rightStoplightStatus = "Red"
            stoplightStatus.leftStoplightStatus = "Green"
            clientStoplight.leftIsOpen = True

    elif clientStoplight.currentTime > clientStoplight.stayOpenTill - yellowTime:
        if clientStoplight.leftIsOpen == True:
            stoplightStatus.leftStoplightStatus = "Yellow"

        else:
            stoplightStatus.rightStoplightStatus = "Yellow"

    clientStoplight.lastSentData = stoplightStatus
    stoplightDict[socketId] = clientStoplight

    sentData = {}
    sentData["leftStoplightStatus"] = stoplightStatus.leftStoplightStatus
    sentData["rightStoplightStatus"] = stoplightStatus.rightStoplightStatus
    print(
        "Tempo atual "
        + str(clientStoplight.currentTime)
        + " Ficando aberto até: "
        + str(clientStoplight.stayOpenTill)
    )
    print(
        "Processou dados dos semaforos, carros na esquerda: "
        + str(clientStoplight.carCountLeft)
        + " e carros na direita: "
        + str(clientStoplight.carCountRight)
    )
    print(
        "Enviando dados dos semaforos, prioridade para a esquerda em "
        + str(clientStoplight.priorityLeft)
    )

    await asyncio.sleep(1)  # sleep for 5 seconds before returning message
    return json.dumps(sentData)


start_server = websockets.serve(handler, "localhost", 8001, max_size=2160000)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
