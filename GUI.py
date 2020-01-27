from PIL import Image, ImageTk
import tkinter as tk
import threading
import cv2
import os
import pickle
import Capstone.NN as nn
import tensorflow as tf
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelBinarizer
from sklearn.metrics import classification_report
import matplotlib.pylab as plt

faceCascade = cv2.CascadeClassifier('Cascades/haarcascade_frontalface_default.xml')

class Application:
    def __init__(self, dataPath = "./"):
        """
            Initialize application which uses OpenCV + Tkinter. It displays video frame and buttons.
        """
        self.vs = cv2.VideoCapture(0)
        self.dataPath = dataPath  # store output path
        self.current_image = None  # current image from the camera
        self.lastFace = None
        self.count = 0
        self.uname = None
        self.rec = False            # flag to use recognizer or not

        self.model = tf.keras.models.load_model('newModel.h5')
        self.lb = self.load("lb")
        print("[INFO] models loaded...")

        self.root = tk.Tk()  # initialize root window
        self.root.title("Face Detective")  # set window title

        # self.destructor function gets fired when the window is closed
        self.root.protocol('WM_DELETE_WINDOW', self.destructor)

        self.panel = tk.Label(self.root)  # initialize video panel
        self.panel.pack(padx=10, pady=10)

        frame1 = tk.Frame(self.root)
        frame1.pack(side="left")
        nameLabel = tk.Label(frame1, text='User Name:')
        nameLabel.pack(fill="none", side="left", expand=False, padx=10, pady=10)
        self.nameEntry = tk.Entry(frame1)
        self.nameEntry.pack(fill="none", side="left", expand=True, padx=10, pady=10)
        btn1 = tk.Button(frame1, text="Add User", command=self.addUser)
        btn1.pack(fill="none", side="left", expand=True, padx=10, pady=10)

        frame2 = tk.Frame(self.root)
        frame2.pack(side="bottom")
        btn2 = tk.Button(frame2, text="Train Recognizer", command=self.trainNeural)
        btn2.pack(fill="none", side="right", expand=True, padx=10, pady=10)
        btn3 = tk.Button(frame2, text="Toggel Recognizer", command=self.toggelRec)
        btn3.pack(fill="none", side="right", expand=True, padx=10, pady=10)
        btn4 = tk.Button(frame2, text="Exit", command=self.destructor)
        btn4.pack(fill="none", side="right", expand=True, padx=10, pady=10)

        self.stopEvent = threading.Event()
        self.thread = threading.Thread(target=self.videoLoop, args=())
        self.thread.start()

    def videoLoop(self):
        """
            Get frame from the video stream, detect a face, and show it in tkinter GUI
        """
        ref, frame = self.vs.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # face detection
        faces = faceCascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(20, 20))
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
            roi_color = frame[y:y + h, x:x + w]
            # saving the last face everytime we have a face
            self.lastFace = gray[y:y+h, x:x+w]

        # TODO: need to handle no face detected error
        if self.count <= 50 and self.count != 0:
            self.addUser()
        if self.count > 50:
            print("[INFO] Face Added to folder")
            self.count = 0

        if ref:
            frame = cv2.flip(frame, 1)
            if self.rec == True:    # started to recognize
                image = cv2.resize(self.lastFace, (30, 30))
                image = image.astype("float") / 255.0
                image = image.reshape(1, *image.shape, 1)
                preds = self.model.predict(image)
                i = preds.argmax(axis=1)[0]
                label = self.lb.classes_[i]

                # draw the class label + probability on the output image
                text = "{}: {:.2f}%".format(label, preds[0][i] * 100)
                cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 1, True)

            # displaying in the GUI
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            self.current_image = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=self.current_image)  # convert image for tkinter
            self.panel.imgtk = imgtk  # anchor imgtk so it does not be deleted by garbage-collector
            self.panel.config(image=imgtk)  # show the image
        self.root.after(30, self.videoLoop)  # call the same function after 30 milliseconds

    def toggelRec(self):
        if self.rec == True:
            self.rec = False
        else:
            self.rec = True

    def trainNeural(self):
        """
            takes the pictures taken and use it to train the neural network architecture model
            saves the trained model
        """
        print("[INFO] initializing train...")
        f = nn.FaceNeural()
        # load images for training
        path = "C:/Users/sagar/Desktop/CSC485/Capstone/dataset/"
        data, labels, numCal = f.load_images(path)

        (trainX, testX, trainY, testY) = train_test_split(data, labels, test_size=0.25, random_state=42)

        print("[INFO] data split...")
        # change to arrays instead of using list for input
        trainX = np.array(trainX)
        testX = np.array(testX)
        trainY = np.array(trainY)
        testY = np.array(testY)

        # one hot encoding
        lb = LabelBinarizer()
        trainY = lb.fit_transform(trainY)  # fit finds all unique class labels
        testY = lb.transform(testY)  # no fit needed as class labels already found

        # change labels to one hot vectors
        trainY = tf.keras.utils.to_categorical(trainY, numCal)
        testY = tf.keras.utils.to_categorical(testY, numCal)

        # model architecture code
        print("[INFO] building architecture...")

        model = tf.keras.models.Sequential()
        model.add(tf.keras.layers.Conv2D(1024, (3, 3), input_shape=(30, 30, 1), name='inputLayer', activation="relu"))
        model.add(tf.keras.layers.Conv2D(512, (3, 3), name='hiddenLayer1', activation="relu"))
        model.add(tf.keras.layers.Flatten())
        model.add(tf.keras.layers.Dense(numCal, name='outputLayer', activation="softmax"))

        model.summary()

        lr = 0.0000000001
        epochs = 1
        batch = 10  # size of group of data to pass through the network

        # print(trainY)
        print("[INFO] training network...")

        # TODO: use categorical_crossentropy function as number of users increases
        adam = tf.keras.optimizers.Adam(learning_rate=lr, beta_1=0.9, beta_2=0.999, amsgrad=False)
        model.compile(loss="categorical_crossentropy", optimizer='adam', metrics=["accuracy"])
        # train or fit the model to the data
        print(len(trainX), len(testX), len(trainY), len(testY), trainX.shape)

        H = model.fit(trainX, trainY, validation_data=(testX, testY), epochs=epochs)

        # evaluate the network
        print("[INFO] evaluating network...")

        predictions = model.predict(testX)
        print(classification_report(testY.argmax(axis=1), predictions.argmax(axis=1), target_names=lb.classes_))

        # plot the training loss and accuracy
        N = np.arange(0, epochs)
        plt.style.use("ggplot")
        plt.figure()
        plt.plot(N, H.history["loss"], label="train_loss")
        plt.plot(N, H.history["val_loss"], label="val_loss")
        plt.plot(N, H.history["accuracy"], label="train_acc")
        plt.plot(N, H.history["val_accuracy"], label="val_acc")
        plt.title("Training Loss and Accuracy (Simple NN)")
        plt.xlabel("Epoch #")
        plt.ylabel("Loss/Accuracy")
        plt.legend()
        plt.show()
        # plt.savefig("plot.jpg")

        print("[INFO] evaluation done...")

        model.save('C:/Users/sagar/Desktop/CSC485/Capstone/newModel.h5')
        self.saveLB("lb", lb)
        print("[INFO] serializing network and label binarizer done...")

    def addUser(self):
        """
            takes username, takes face pictures of the user present, and saves them
            counts 100
        """
        if self.count == 0:
            # print("[INFO] adding User...")
            # self.uname = input('\nenter user name and press <return> ==>  ')  # user name, string
            # print("\n[INFO] Initializing face capture. Look the camera and wait ...")
            self.uname = self.nameEntry.get()
            print("[INFO] adding User..."+self.uname)
            self.dataPath = "dataset/" + self.uname + "/"
        if not os.path.exists(self.dataPath):
            os.makedirs(self.dataPath)
        cv2.imwrite(self.dataPath + self.uname + '.' + str(self.count) + ".jpg", cv2.resize(self.lastFace, (30, 30)))
        self.count+=1

    def destructor(self):
        """ Destroy the root object and release all resources """
        print("[INFO] closing...")
        self.root.destroy()
        self.vs.release()  # release web camera
        cv2.destroyAllWindows()  # it is not mandatory in this application

    # methods for saving and loading binarizer
    def saveLB(self, filename, lb):
        """
        Saves the classifier to a pickle
          Args:
            filename: The name of the file (no file extension necessary)
        """
        with open(filename + ".pkl", 'wb') as f:
            f.write(pickle.dumps(lb))
            f.close()

    def load(self, filename):
        """
        A static method which loads the classifier from a pickle
          Args:
            filename: The name of the file (no file extension necessary)
        """
        with open(filename + ".pkl", 'rb') as f:
            return pickle.load(f)

# start the app
print("[INFO] starting...")
pba = Application()
pba.root.mainloop()