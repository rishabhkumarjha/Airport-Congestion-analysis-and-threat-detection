import cv2
import threading
import os
import numpy as np
from PIL import Image
import socket
import time

# globals
sock = socket.socket()
sock.connect(("192.168.43.238", 420))
sock.send("IP")

feedInfo = []   # list containing all info about the feeds
feedattr = open("feeds.addr", "r")
x = feedattr.readlines(-1)
for l in x:
    feedInfo.append(l.split(","))
print(feedInfo)
del x
feedattr.close()
del feedattr
threatFrame = []
cv2.namedWindow("Threats", cv2.WINDOW_GUI_NORMAL)
globFrames = []         # these frames are required to display all thread frames
for i in range(0, len(feedInfo)):
    globFrames.append(None)
    cv2.namedWindow(feedInfo[i][1], cv2.WINDOW_OPENGL)

# load face recognizer
print("loading face recognizer database")
faceRecognizer = cv2.face.createLBPHFaceRecognizer()
faceDetect = cv2.CascadeClassifier("cascades/haarcascade_frontalface_default.xml")

labels = os.listdir('red_corner')
img = []    #store list of numpy images
labelint=[] #store converted labels in terms of numbers
for lab in labels:
    imgpil = Image.open("red_corner/"+lab).convert('L')
    simage = np.array(imgpil, 'uint8')  #subject image
    faces = faceDetect.detectMultiScale(simage)
    for (x,y,w,h) in faces:
        img.append(simage[y:y+h, x:x+w])
        labelint.append(int(lab.split(".")[0].replace("subject", "")))

print("training...")
print(type(labels[1]))
print(type(img[12]))
labelint = np.array(labelint)
faceRecognizer.train(img, labelint)
print("training completed")


feature_params = dict( maxCorners = 50, qualityLevel = 0.5, minDistance = 30, blockSize = 7)
    #params for lucas Kanade optical flow ref: opencv docs
lk_params = dict(winSize = (15,15),maxLevel = 2,criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,10,0.03))

class ServiceTracker(threading.Thread):
    flag1 = 0
    oldFrame = None
    p0 = np.array([[50,50]],dtype=np.float32)
    p1 = None
    def __init__(self, frame,indexg):
        threading.Thread.__init__(self)
        self.frame = frame
        self.start_time = time.time()
        self.camindex=indexg
        print("cam index : " + str(self.camindex))

    def trackMyGuy(self):
        while True:
            if self.flag1 == 0:
                self.frame = cv2.cvtColor(globFrames[self.camindex], cv2.COLOR_BGR2GRAY)
                self.oldFrame = self.frame

            if self.flag1 == 1:
                self.frame = globFrames[self.camindex]
                self.frame = cv2.cvtColor(self.frame,cv2.COLOR_BGR2GRAY)
                self.p1, st, err = cv2.calcOpticalFlowPyrLK(self.oldFrame,self.frame,self.p0,None,**lk_params)

                good_new = self.p1
                good_old = self.p0
                #print("good")

                #x, y = good_new.ravel()
                x=self.p1[0][0]
                #print("good new : " + str(self.p1[0]))
                if(x<10):
                    print("track time : "+str(self.camindex)+" " + str((time.time()-self.start_time)))
                    #sock.send('\n{'+'\''+feedInfo[self.camindex][1]+'\''+':'+str(3*350*(time.time()-self.start_time)).split('.')[0]+'}')
                    #print (str('\n{'+'\''+feedInfo[self.camindex][1]+'\''+':'+str(3*350*(time.time()-self.start_time)).split('.')[0]+'}').encode())
                    p0 = np.array([[60, 40]], dtype=np.float32)
                    self.start_time = time.time()
                if(time.time()-self.start_time >= 60):
                    print("end of tracking at 30")
                    p0 = np.array([[60, 40]], dtype=np.float32)
                    self.start_time = time.time()
                self.oldFrame = self.frame.copy()
                #p0 = good_new.reshape(-1, 1, 2)
                self.p0 = self.p1
            if self.flag1 == 0:
                self.flag1 = 1
                print("flag set to 1")

    def run(self):
        self.trackMyGuy()


class ThreatDetector(threading.Thread):
    # face = None

    def __init__(self, face):
        threading.Thread.__init__(self)
        self.face = face

    def run(self):
        print("in run ")
        threatFrame = self.face
        print(threatFrame)
        self.face = cv2.cvtColor(self.face, cv2.COLOR_BGR2GRAY)
        match_made,confidence = faceRecognizer.predict(self.face)
        if confidence < 50:
            os.system("spd-say 'threat detected'")
            threatFrame = self.face
            cv2.imshow("Threats", threatFrame)
        print("x is : ")
        print(confidence)


class Feed (threading.Thread):
    numberOfPeople = 0      # keeps count of people in single video feed
    frame = None
    detected_people = 0

    def __init__(self, camname, cap, cascade_addr, triml, trimu, index):
        threading.Thread.__init__(self)     # its customary to init Thread class which Feed inherits
        self.camname = camname
        self.cap = cap
        self.cascade_addr = cascade_addr
        self.people_detector = cv2.CascadeClassifier(cascade_addr)  # cascade classifier for people
        self.triml = triml
        self.trimu = trimu
        self.index = index
        self.strt_time = time.time()

    def people_count(self):
        cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        self.detected_people = self.people_detector.detectMultiScale(self.frame, scaleFactor=1.03, minSize=(40, 60), maxSize=(150, 180))
        self.numberOfPeople = len(self.detected_people)
        print("number of people @ " + self.camname + " " + str(self.numberOfPeople))
        sock.send(str(self.camname)+":"+str(self.detected_people))
        for (x, y, w, h) in self.detected_people:
            cv2.rectangle(globFrames[self.index], (x, y), (x+w, y+h), (0, 255, 0), 2)
        face = faceDetect.detectMultiScale(self.frame)
        for (x, y, w, h) in face:
            self.match_face(self.frame[y:y+h, x:x+w])

    def detect_baggage(self):
        pass

    def match_face(self, face):
        matchtd = ThreatDetector(face)
        matchtd.start()

    def run(self):
        ret, self.frame = self.cap.read()
        print ("speed fps : " + str((self.cap.get(cv2.CAP_PROP_POS_FRAMES)/(time.time()-self.strt_time))/self.cap.get(cv2.CAP_PROP_FPS)))
        self.frame = self.frame[self.triml:self.trimu, :]
        globFrames[self.index] = self.frame
        trackthd = ServiceTracker(self.frame, self.index)
        trackthd.start()
        cnt=0
        while ret:
            print ("speed fps : " + str(
                (self.cap.get(cv2.CAP_PROP_POS_FRAMES) / (time.time() - self.strt_time)) / self.cap.get(
                    cv2.CAP_PROP_FPS)))
            cnt += 1
            if cnt % 350 == 0:
                self.people_count()
                cnt = 0                       # if an error look here
            ret, self.frame = self.cap.read()           # TODO: catch exception for None frame  here

            self.frame=self.frame[self.triml:self.trimu, :]
            globFrames[self.index] = self.frame

        if self.frame==None:
            globFrames[self.index] = cv2.imread('SignalLost.png')
            self.frame = globFrames[self.index]
            print("signal Lost")
        #cv2.destroyWindow(self.camname)

for i in range(0, len(feedInfo)):
    feed_thd = Feed(feedInfo[i][1], cv2.VideoCapture(feedInfo[i][0]), feedInfo[i][2], int(feedInfo[i][3]), int(feedInfo[i][4]), int(feedInfo[i][5]))
    feed_thd.start()

while True:
    for i in range(0, len(feedInfo)):
        if globFrames[i] is not None:
            cv2.imshow(feedInfo[i][1], globFrames[i])
    cv2.waitKey(1)