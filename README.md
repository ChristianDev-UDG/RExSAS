# RExSAS
RExSAS is a software framework for Rehabilitation Exoskeletons with Signal Acquisition Systems which acquires EEG signals in real time in order to control a graphic user interface for the therapy selection. This framework could be helpful in multiple tasks since it shows how to acquire and process raw EEG for controlling robotic systems. 

It starts by creating a graphic user interface (GUI) that helps the user visualize the speed options available for rehabilitation. The process for the option selection is described below:

- The user wears the Exoskeleton and the EEG signal acquisition hardware (electrodes, helmet, electronic card for amplifying and pre process the signal, etc.).
- The user visualizes the GUI and decide which speed is the one desired.
- For iteration among options, the user must blink once per option.
- Once the indicator is over the option desired, the user shall close his eyes in order to produce the neural activity desired in the parieto-occipital lobes, which in this case, is the amplification of alpha waves, inducing a relaxation state for calming down and provide security during the use of the electromechanical device.
- The color of the selected option will start to get greener and greener depending on the behavior of the neural activity and the signal processing developed for the brain computer interface, which cover a percentage of what the system establishes for ackoledging the selection made.
- Once it gets to 100%, the BCI acknowledges the selection and starts the rehabilitation procedure with the exoskeleton.
- Each therapy procedure lasts for about 60 seconds, and starts the signal acquisition system all over again.

This work is licensed under the MIT License, which grants anyone the freedom to use, modify, distribute, and even sell the software, with the only condition being that the original copyright and license notice must be included in all copies. 
