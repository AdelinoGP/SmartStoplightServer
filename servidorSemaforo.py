from uuid import UUID
import cv2
import os
import asyncio
import websockets
import json
from pathlib import Path

class DataSemaforo:
    estadoSemaforo1 = False
    estadoSemaforo2 = True
    prioridadeSemaforo1 = 0.5
    tempoSemaforoMax = 30
    tempoSemaforoAmarelo = 3

connected = set[websockets.WebSocketServerProtocol]()

semaforos = dict[UUID, DataSemaforo]()


async def handler(websocket:websockets.WebSocketServerProtocol):
    # Register.
    connected.add(websocket)
    semaforos[websocket.id] = DataSemaforo()
    try:
        consumer_task = asyncio.create_task(consumer_handler(websocket))
        producer_task = asyncio.create_task(producer_handler(websocket))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        # Unregister
        semaforos.pop(websocket.id)
        connected.remove(websocket)

async def consumer_handler(websocket:websockets.WebSocketServerProtocol):
    async for message in websocket:
        await consumer(message, websocket.id)

async def producer_handler(websocket:websockets.WebSocketServerProtocol):
    while True:
        message = await producer(websocket.id)
        await websocket.send(message)

async def consumer(message:websockets.Data, socketId:UUID):
    print(message)

async def producer(socketId:UUID):
    message = "Hello, World!"
    await asyncio.sleep(5) # sleep for 5 seconds before returning message
    return message

async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()  # run forever

asyncio.run(main())