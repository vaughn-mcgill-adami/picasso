"""
    picasso.simulate
    ~~~~~~~~~~~~~~~~

    Simulate single molcule fluorescence data

    :author: Maximilian Thomas Strauss, 2016
    :copyright: Copyright (c) 2016 Jungmann Lab, MPI of Biochemistry
"""
import numpy as _np
from . import io as _io
#from . import CONFIG as _CONFIG

#if _CONFIG:
#    cx = _CONFIG['3D Calibration']['X Coefficients']
#    cy = _CONFIG['3D Calibration']['Y Coefficients']
#    magfac = _CONFIG['3D Calibration']['Magnification Factor']
#else:
magfac = 0.76
cx = [3.1638306844743706e-17, -2.2103661248660896e-14, -9.775815406044296e-12, 8.2178622893072e-09, 4.91181990105529e-06, -0.0028759382006135654, 1.1756537760039398]
cy = [1.710907877866197e-17, -2.4986657766862576e-15, -8.405284979510355e-12, 1.1548322314075128e-11, 5.4270591055277476e-06, 0.0018155881468011011, 1.011468185618154]


def calculate_zpsf(z, cx, cy):
    z = z/magfac
    z2 = z * z
    z3 = z * z2
    z4 = z * z3
    z5 = z * z4
    z6 = z * z5
    wx = cx[0]*z6 + cx[1]*z5 + cx[2]*z4 + cx[3]*z3 + cx[4]*z2 + cx[5]*z + cx[6]
    wy = cy[0]*z6 + cy[1]*z5 + cy[2]*z4 + cy[3]*z3 + cy[4]*z2 + cy[5]*z + cy[6]

    return (wx, wy)

def saveInfo(filename, info):
    _io.save_info(filename, [info], default_flow_style=True)

def noisy(image, mu, sigma):        #Add gaussian noise to an image.
    row, col= image.shape  #Variance for _np.random is 1
    gauss = sigma*_np.random.normal(0,1,(row, col)) + mu
    gauss = gauss.reshape(row, col)
    noisy = image + gauss
    noisy[noisy < 0] = 0
    return noisy

def noisy_p(image,mu): #Add poissonian noise to an image
    poiss = _np.random.poisson(mu,image.shape).astype(float)
    noisy = image + poiss
    return noisy


def paintgen(meandark, meanbright, frames, time, photonrate, photonratestd, photonbudget,simple): #Paint-Generator: Generates on and off-traces for given parameters. Calculates the number of Photons in each frame for a binding site
    meanlocs = 4*int(_np.ceil(frames*time/(meandark+meanbright))) #This is an estimate for the total number of binding events
    if meanlocs < 10:
        meanlocs = meanlocs*10

    if simple:
        dark_times = _np.random.exponential(meandark, meanlocs)
        bright_times = _np.random.exponential(meanbright, meanlocs)
    else:
        #Generate a pool of dark and brighttimes
        dark_times_pool = _np.random.exponential(meandark, meanlocs)
        bright_times_pool = _np.random.exponential(meanbright, meanlocs)

        darksum = _np.cumsum(dark_times_pool)
        maxlocdark = _np.argmax(darksum>(frames*time))+1

        #Simulate binding and unbinding and consider blocked binding sites
        dark_times = _np.zeros(maxlocdark)
        bright_times = _np.zeros(maxlocdark)

        dark_times[0] = dark_times_pool[0]
        bright_times[0] = bright_times_pool[0]

        for i in range(1,maxlocdark):
            bright_times[i] = bright_times_pool[i]

            dark_time_temp = dark_times_pool[i]-bright_times_pool[i]
            while dark_time_temp < 0:
                _np.delete(dark_times_pool,i)
                dark_time_temp +=dark_times_pool[i]

            dark_times[i] = dark_time_temp

    events = _np.vstack((dark_times, bright_times)).reshape((-1,), order='F') # Interweave dark_times and bright_times [dt,bt,dt,bt..]
    simulatedmeandark = _np.mean(events[::2])
    simulatedmeanbright = _np.mean(events[1::2])
    eventsum = _np.cumsum(events)
    maxloc = _np.argmax(eventsum>(frames*time)) #Find the first event that exceeds the total integration time
    ## CHECK Trace
    if _np.mod(maxloc,2): #uneven -> ends with an OFF-event
        onevents = int(_np.floor(maxloc/2));
    else: #even -> ends with bright event
        onevents = int(maxloc/2);
    bright_events = _np.floor(maxloc/2); #number of bright_events

    #AN ON-EVENT MIGHT BE LONGER THAN THE MOVIE, SO ALLOCATE MORE MEMORY, AS AN ESTIMATE: MEANBRIGHT/time*10
    photonsinframe = _np.zeros(int(frames+_np.ceil(meanbright/time*20)))

    ## CALCULATE PHOTON NUMBERS
    for i in range(1,maxloc,2):
        photons = _np.round(_np.random.normal(photonrate,photonratestd)*time) #Number of Photons that are emitted in one frame

        if photons < 0:
            photons = 0

        tempFrame = int(_np.floor(eventsum[i-1]/time)); #Get the first frame in which something happens in on-event
        onFrames = int(_np.ceil((eventsum[i]-tempFrame*time)/time)); #Number of frames in which photon emittance happens

        if photons*onFrames > photonbudget:
            onFrames = int(_np.ceil(photonbudget/(photons*onFrames)*onFrames)) #Reduce the number of on-frames once the photonbudget is reached

        for j in range(0,(onFrames)): #LOOP THROUGH ALL ONFRAMES

            if onFrames == 1: #CASE 1: ALL PHOTONS ARE EMITTED IN ONE FRAME
                photonsinframe[1+tempFrame]=int(_np.random.poisson(((tempFrame+1)*time-eventsum[i-1])/time*photons))
            elif onFrames == 2: #CASE 2: ALL PHOTONS ARE EMITTED IN TWO FRAMES
                emittedphotons = (((tempFrame+1)*time-eventsum[i-1])/time*photons)
                if j == 1: # PHOTONS IN FIRST ONFRAME
                    photonsinframe[1+tempFrame]=int(_np.random.poisson(((tempFrame+1)*time-eventsum[i-1])/time*photons))
                else: # PHOTONS IN SECOND ONFRAME
                    photonsinframe[2+tempFrame]=int(_np.random.poisson((eventsum[i]-(tempFrame+1)*time)/time*photons))
            else: # CASE 3: ALL PHOTONS ARE EMITTED IN THREE OR MORE FRAMES
                if j == 1:
                    photonsinframe[1+tempFrame]=int(_np.random.poisson(((tempFrame+1)*time-eventsum[i-1])/time*photons))  #Indexing starts with 0
                elif j == onFrames:
                    photonsinframe[onFrames+tempFrame]=int(_np.random.poisson((eventsum(i)-(tempFrame+onFrames-1)*time)/time*photons))
                else:
                    photonsinframe[tempFrame+j]=int(_np.random.poisson(photons))

        totalphotons = _np.sum(photonsinframe[1+tempFrame:tempFrame+1+onFrames])
        if totalphotons > photonbudget:
            photonsinframe[onFrames+tempFrame]=int(photonsinframe[onFrames+tempFrame]-(totalphotons-photonbudget))

    photonsinframe = photonsinframe[0:frames] #Catch exception if a trace should be longer than the movie
    timetrace = events[0:maxloc]

    if onevents > 0:
        spotkinetics = [onevents,sum(photonsinframe>0),simulatedmeandark,simulatedmeanbright]
    else:
        spotkinetics = [0,sum(photonsinframe>0),0,0]
    #spotkinetics is an output variable, that gives out the number of on-events, the number of localizations, the mean of the dark and bright times
    return photonsinframe,timetrace,spotkinetics

def distphotons(structures,itime,frames,taud,taub,photonrate,photonratestd,photonbudget,simple):

    time = itime
    meandark = int(taud)
    meanbright = int(taub)

    bindingsitesx = structures[0,:]
    bindingsitesy = structures[1,:]
    nosites  = len(bindingsitesx) # number of binding sites in image

    #PHOTONDIST: DISTRIBUTE PHOTONS FOR ALL BINDING SITES

    photonposall = _np.zeros((2,0))
    photonposall = [1,1]

    photonsinframe,timetrace,spotkinetics = paintgen(meandark,meanbright,frames,time,photonrate,photonratestd,photonbudget,simple)

    return photonsinframe, spotkinetics

def convertMovie(runner, photondist,structures,imagesize,frames,psf,photonrate,background, noise, mode3Dstate):

    pixels = imagesize

    bindingsitesx = structures[0,:]
    bindingsitesy = structures[1,:]
    bindingsitesz = structures[4,:]
    nosites  = len(bindingsitesx) # number of binding sites in image


    #FRAMEWISE SIMULATION OF PSF
    #ALL PHOTONS FOR 1 STRUCTURE IN ALL FRAMES
    edges = range(0,pixels+1)
    #ALLCOATE MEMORY
    movie = _np.zeros(shape=(frames,pixels,pixels), dtype='<u2')

    flag = 0
    photonposframe = _np.zeros((2,0))

    for i in range(0,nosites):
        tempphotons = photondist[i,:]
        photoncount = int(tempphotons[runner])

        if mode3Dstate:
            wx, wy = calculate_zpsf(bindingsitesz[i], cx, cy)
            cov = [[wx*wx, 0], [0, wy*wy]]
        else:
            cov = [[psf*psf, 0], [0, psf*psf]]

        if photoncount > 0:
            flag = flag+1
            mu = [bindingsitesx[i],bindingsitesy[i]]
            photonpos = _np.random.multivariate_normal(mu, cov, photoncount)
            if flag == 1:
                photonposframe = photonpos
            else:
                photonposframe = _np.concatenate((photonposframe,photonpos),axis=0)

        #HANDLE CASE FOR NO PHOTONS DETECTED AT ALL IN FRAME
    if photonposframe.size == 0:
        simframe = _np.zeros((pixels,pixels))
    else:
        xx = photonposframe[:,0]
        yy = photonposframe[:,1]
        simframe, xedges, yedges = _np.histogram2d(yy,xx,bins=(edges,edges))
        simframe = _np.flipud(simframe) # to be consistent with render
    #simframenoise = noisy(simframe,background,noise)
    simframenoise = noisy_p(simframe,background)
    simframenoise[simframenoise > 2**16-1] = 2**16-1
    simframeout=_np.round(simframenoise).astype('<u2')

    return simframeout



def saveMovie(filename,movie,info):
    _io.save_raw(filename, movie, [info])


def defineStructure(structurexxpx,structureyypx,structureex,structure3d,pixelsize): #Function to store the coordinates of a structure in a container. The coordinates wil be adjustet so that the center of mass is the origin
    structurexxpx = structurexxpx-_np.mean(structurexxpx)
    structureyypx = structureyypx-_np.mean(structureyypx)
    #from px to nm
    structurexx = []
    for x in structurexxpx:
        structurexx.append(x/pixelsize)
    structureyy = []
    for x in structureyypx:
        structureyy.append(x/pixelsize)

    structure = _np.array([structurexx, structureyy,structureex,structure3d]) #FORMAT: x-pos,y-pos,exchange information

    return structure

def generatePositions(number,imagesize,frame,arrangement): #GENERATE A SET OF POSITIONS WHERE STRUCTURES WILL BE PLACED

    if arrangement==0:
        spacing = _np.ceil((number**0.5))
        linpos = _np.linspace(frame,imagesize-frame,spacing)
        [xxgridpos,yygridpos]=_np.meshgrid(linpos,linpos)
        xxgridpos = _np.ravel(xxgridpos)
        yygridpos = _np.ravel(yygridpos)
        xxpos = xxgridpos[0:number]
        yypos = yygridpos[0:number]
        gridpos =_np.vstack((xxpos,yypos))
        gridpos = _np.transpose(gridpos)
    else:
        gridpos = (imagesize-2*frame)*_np.random.rand(number,2)+frame

    return gridpos

def rotateStructure(structure): #ROTATE A STRUCTURE RANDOMLY
    angle_rad = _np.random.rand(1)*2*3.141592
    newstructure = _np.array([(structure[0,:])*_np.cos(angle_rad)-(structure[1,:])*_np.sin(angle_rad),
                (structure[0,:])*_np.sin(angle_rad)+(structure[1,:])*_np.cos(angle_rad),
                structure[2,:],structure[3,:]])
    return newstructure

def incorporateStructure(structure,incorporation): #CONSIDER STAPLE INCORPORATION
    newstructure = structure[:,(_np.random.rand(structure.shape[1])<incorporation)]
    return newstructure

def randomExchange(pos): # RANDOMLY SHUFFLE EXCHANGE PARAMETERS ('RANDOM LABELING')
    arraytoShuffle = pos[2,:]
    _np.random.shuffle(arraytoShuffle)
    newpos = _np.array([pos[0,:],pos[1,:],arraytoShuffle,pos[3,:]])
    return newpos

def prepareStructures(structure,gridpos,orientation,number,incorporation,exchange): #prepareStructures: Input positions, the structure definition, consider rotation etc.
    newpos = []
    oldstructure = _np.array([structure[0,:],structure[1,:],structure[2,:],structure[3,:]])

    for i in range(0,len(gridpos)):#LOOP THROUGH ALL POSITIONS
        if orientation == 0:
            structure = oldstructure
        else:
            structure = rotateStructure(oldstructure)

        if incorporation == 1:
            pass
        else:
            structure = incorporateStructure(structure,incorporation)

        newx = structure[0,:]+gridpos[i,0]
        newy = structure[1,:]+gridpos[i,1]
        newstruct = _np.array([newx,newy,structure[2,:],structure[2,:]*0+i,structure[3,:]])
        if i == 0:
            newpos = newstruct
        else:
            newpos = _np.concatenate((newpos,newstruct),axis=1)

    if exchange == 1:
        newpos = randomExchange(newpos)

    return newpos
