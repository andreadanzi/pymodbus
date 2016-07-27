# -*- coding: utf-8 -*-
#!/usr/bin/env python
         
class VolumeStep(object):
    """
    Volume Step
    """    
    def __init__(self, name, maxVolume,percPtest, tolerance = 0.01, bUpstage = False, Pa = None):
        ''' Initializes a new instance of a Volume Step.
    
        '''
        self.name   = name
        self.maxVolume = maxVolume
        self.bRAchieved = False
        self.bStopGrouting = False
        self.bIntermittent = False
        self.nextMixType = False
        self.bVN = False
        self.percPtest = percPtest
        self.tolerance = tolerance
        self.bUpstage = bUpstage
        self.Pa = None

    def __str__(self):
        return "name=%s-maxVolume=%f-percPtest=%f\nbRAchieved %s, bStopGrouting %s, nextMixType %s, bVN %s, bIntermittent %s" % (self.name, self.maxVolume, self.percPtest,self.bRAchieved,self.bStopGrouting,self.nextMixType,self.bVN, self.bIntermittent)

        
    def check_pressure(self, Peff,refPress ):
        if Peff < self.percPtest*refPress:
            self.nextMixType = True
            self.bRAchieved = False
            self.bStopGrouting = True
        else:
            self.bVN = True
        return self.bStopGrouting

class VolumeStep4(VolumeStep):
    
    def setPercTest2(self,  percTest2):
        self.percTest2 = percTest2
        
    def check_pressure(self, Peff,refPress ):
        if self.bUpstage and  Peff > self.Pa:
            self.bRAchieved = True
            self.bStopGrouting = True
        elif Peff < self.percPtest*refPress:
            self.nextMixType = True
            self.bRAchieved = False
            self.bStopGrouting = True
        elif Peff < self.percTest2*refPress:
            self.bIntermittent = True
            self.bStopGrouting = True
        else:
            self.bVN = True                
        return self.bStopGrouting   


class VolumeStep5(VolumeStep):
        
    def check_pressure(self, Peff,refPress ):
        print Peff,refPress
        if self.bUpstage and  Peff > self.Pa:
            self.bRAchieved = True
            self.bStopGrouting = True
        elif Peff < self.percPtest*refPress:
            self.bIntermittent = True
            self.bStopGrouting = True
        else:
            self.bVN = True                
        return self.bStopGrouting 
       
class GroutingStep(object):
    """
    Grouting step
    """
    def __init__(self, listVolumes, refPress, startingVolume = 0, tolerance = 0.01):
        ''' Initializes a new instance of a Grouting Step.
    
        :param volumes: list of increasing voulume steps
        '''
        self.listVolumes   = listVolumes
        self.volume = startingVolume
        self.tolerance = tolerance
        self.refPress = refPress
        self.current_volume_step = self.listVolumes[0]
        self.step = 1
        for item in self.listVolumes:
            item.tolerance = tolerance

    def add_volume(self,vol):
        self.volume += vol
        return self.volume
        
    def check_grouting(self,Peff):
        bStop = False
        if Peff >= self.refPress - self.tolerance:
            bStop = True
            self.current_volume_step.bStopGrouting = True
            self.current_volume_step.bRAchieved = True
        else:
            for idx, vol in enumerate(self.listVolumes):
                if self.volume > vol.maxVolume:
                    self.step = idx + 1
                    bStop = vol.check_pressure(Peff,self.refPress)
                    self.current_volume_step = vol
        return bStop
        
R = 30
print "\n##################### MIX_A\n"
# MIX_A 
last_volume = 0
volumes=[]
v=VolumeStep("V1",0.1*1000.0,0.1)
volumes.append(v)
v=VolumeStep("V2",0.3*1000.0,0.5)
volumes.append(v)
v=VolumeStep("V3",0.5*1000.0,0.8)
volumes.append(v)
gstep = GroutingStep(volumes, R)
bStop = False
incrP=0.
while not bStop:
    incrP += .25
    last_volume = gstep.add_volume(6)
    print last_volume
    bStop = gstep.check_grouting(incrP)
    print gstep.current_volume_step
    print gstep.step, incrP

print "\n##################### MIX_B\n"
#  MIX_B
volumes=[]
v=VolumeStep("V1",0.1*1000.0,0.1)
volumes.append(v)
v=VolumeStep("V2",0.3*1000.0,0.5)
volumes.append(v)
v=VolumeStep("V3",0.5*1000.0,0.8)
volumes.append(v)
gstep = GroutingStep(volumes, R, last_volume)
bStop = False
while not bStop:
    incrP += .2
    last_volume = gstep.add_volume(10)
    print last_volume
    bStop = gstep.check_grouting(incrP)
    print gstep.current_volume_step
    print gstep.step, incrP

print "\n##################### MIX_C\n"
# MIX_C
volumes=[]
v=VolumeStep4("V4",0.8*1000.0,0.5)
v.setPercTest2(0.8)
volumes.append(v)
gstep = GroutingStep(volumes, R, last_volume)
bStop = False
while not bStop:
    incrP += .8
    last_volume = gstep.add_volume(30)
    print last_volume
    bStop = gstep.check_grouting(incrP)
    print gstep.current_volume_step
    print gstep.step, incrP

print "\n##################### MIX_D\n"
# MIX_D
volumes=[]
v=VolumeStep5("V5",2.0*1000.0,0.8)
volumes.append(v)
gstep = GroutingStep(volumes, R)
bStop = False
while not bStop:
    incrP += .9
    last_volume = gstep.add_volume(30)
    print last_volume
    bStop = gstep.check_grouting(incrP)
    print gstep.current_volume_step    
    print gstep.step, incrP
#TODO verificare con Granata quando fermarsi