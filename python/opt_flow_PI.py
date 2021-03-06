#!/usr/bin/env python
from __future__ import print_function
import sys

#Computer vision
import cv2
import numpy as np
import picamera
import picamera.array

#RaspberryPi Buttons
import RPi.GPIO as GPIO

#OSC
import socket
from txosc import osc
from txosc import sync

#Configure buttons
GPIO.setmode(GPIO.BCM)
GPIO.setup(26, GPIO.IN)
GPIO.setup(19, GPIO.IN)
GPIO.setup(13, GPIO.IN)
GPIO.setup(6, GPIO.IN)

parameters = open('parameters.csv', 'w')

pygameMode = True
if len(sys.argv) > 1:
    pygameMode = False

if pygameMode:
    import pygame

    pygame.init()

    pygame.display.set_caption("OpenCV camera stream on Pygame")
    screen_width = 320
    screen_height = 240

    screen = pygame.display.set_mode([screen_width, screen_height])

#OSC SC client
oscClient = sync.UdpSender("localhost",57120)

camera = picamera.PiCamera()
camera.resolution = (320, 240)
camera.framerate = 18
# set up a video stream
video = picamera.array.PiRGBArray(camera)

button1 = 0
button2 = 0
button3 = 0
button4 = 0

# set up pygame, the library for displaying images
def play_flow(img, flow, step=16):
    h, w = img.shape[:2]
    y, x = np.mgrid[step/2:h:step, step/2:w:step].reshape(2,-1).astype(int)
    fx, fy = flow[y,x].T
    lines = np.vstack([x, y, x+fx, y+fy]).T.reshape(-1, 2, 2)
    lines = np.int32(lines + 0.5)
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.polylines(vis, lines, 0, (255, 0,0))
    for (x1, y1), (x2, y2) in lines:
        cv2.circle(vis, (x1, y1), 1, (0, 255, 0), -1)
    h, w, _ = flow.shape
    left_eye = np.apply_along_axis(np.linalg.norm, 0, flow[:,:w/2]).mean()
    right_eye = np.apply_along_axis(np.linalg.norm, 0, flow[:,w/2:]).mean()
    diff = (left_eye - right_eye)
    diff = diff if np.isfinite(diff) else 0

    # Calculate using angle information
    left_eye_mean_velocity = flow[:,:w/2].mean(axis=1).mean(axis=0)
    right_eye_mean_velocity = flow[:,w/2:].mean(axis=1).mean(axis=0)


    left_eye_mean_velocity_norm = np.linalg.norm(left_eye_mean_velocity)
    right_eye_mean_velocity_norm = np.linalg.norm(right_eye_mean_velocity)

    eyes_cosine = left_eye_mean_velocity.dot(right_eye_mean_velocity.T)/(left_eye_mean_velocity_norm*right_eye_mean_velocity_norm)
    print("Eyes cosine => {}".format(eyes_cosine))

    button1 = GPIO.input(26)
    button2 = GPIO.input(19)
    button3 = GPIO.input(13)
    button4 = GPIO.input(6)

    parameters.write('{}, {}, {}, {}, {}, {}\n'.format(diff, eyes_cosine, button1, button2, button3, button4))
    parameters.flush()

    if pygameMode:
        print("Difference => {}".format(diff))
    if abs(diff)>1:
        msg = osc.Message("/secondSound")
        #detune = float(abs(diff)/10) #detune
        rate = float(abs(diff)/10) #rate
        detune = float(5 + 14*eyes_cosine)
        #rate = 5 + 14*eyes_cosine
        msg.add(detune)
        msg.add(rate)
        msg.add(button1)
        msg.add(button2)
        msg.add(button3)
        msg.add(button4)
        oscClient.send(msg)
    return vis

try:
    camera.capture(video, format="bgr", use_video_port=True)
    prevgray = cv2.cvtColor(video.array, cv2.COLOR_BGR2GRAY)
    video.truncate(0)

    for frameBuf in camera.capture_continuous(video, format ="bgr", use_video_port=True):
        # convert color and orientation from openCV format to GRAYSCALE
        video.truncate(0)
        gray = cv2.cvtColor(frameBuf.array, cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(prevgray, gray, pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
        prevgray = gray
        flow_im = np.fliplr(np.rot90(play_flow(gray, flow)))
        if pygameMode:
            surface = pygame.surfarray.make_surface(flow_im)
            screen.fill([0,0,0])
            screen.blit(surface, (0,0))
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    parameters.close()
                    raise SystemExit


# this is some magic code that detects when user hits ctrl-c (and stops the programme)
except KeyboardInterrupt,SystemExit:
    if pygameMode:
        pygame.quit()
        cv2.destroyAllWindows()
    sys.exit(0)
