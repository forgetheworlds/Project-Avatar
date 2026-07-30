include <waterJet.scad>

motorKV = 1700;
motorV = 12;
motorRPM = motorKV * motorV;
echo ("motor KV", motorKV, "[rmp/V]");
echo ("battery", motorV, "[V]");
echo ("motor max RPM", motorRPM, "[1/min]");

impellerWsurface = impellerChamberD*impellerChamberD*PI/4 - 
                   impellerHubDia*impellerHubDia*PI/4
                   -impellerBlades*impellerWall*(impellerChamberH-impellerHubDia)/2;
echo ("impeler water surface" , impellerWsurface, "[mm^2]");

volumePerRevolution = impellerWsurface*impellerLead;
echo ("Volume per revolution" , volumePerRevolution/1000, "[cm^3]");
impellerChamberSpeed = motorRPM*impellerLead/1000000*60;
echo ("impeller chamber speed" , impellerChamberSpeed, "[km/h]", impellerChamberSpeed*3.6, "[m/s]");

echo ("jet output diameter" , jetOut*2, "[mm]");
jetOutSurface = jetOut*jetOut*PI;
echo ("jet output surface" , jetOutSurface, "[mm^2]");
waterNozzleAccelerationFactor = impellerWsurface/jetOutSurface;
echo ("water nozzle acceleration factor" , waterNozzleAccelerationFactor);
jetOutputSpeed = waterNozzleAccelerationFactor * impellerChamberSpeed;
jetOutputSpeedMpS = jetOutputSpeed / 3.6;
echo ("estimated jet output speed" , jetOutputSpeed, "[km/h]", jetOutputSpeedMpS, "[m/s]");
waterOutputVolumePerSec = jetOutputSpeedMpS*(jetOutSurface/1000); 
echo ("estimated jet output liter" , waterOutputVolumePerSec, "l/s", waterOutputVolumePerSec*60, "[l/m]");
waterOutputPower = waterOutputVolumePerSec*jetOutputSpeedMpS*jetOutputSpeedMpS/2;
echo ("estimated water output power", waterOutputPower, "[W]", waterOutputPower*0.001362, "[HP]");
generalEfficiency = 60/100;
echo ("estimated motor power at ",generalEfficiency*100,"% efficiency", waterOutputPower/generalEfficiency, "[W]", waterOutputPower*0.001362/generalEfficiency, "[HP]");
echo ("estimated motor ESC current at ",generalEfficiency*100,"% efficiency", waterOutputPower/generalEfficiency/motorV, "[A]");
echo ("estimated jet impulse", waterOutputVolumePerSec*jetOutputSpeedMpS, "[N*s]");

hullEfficiency = 40/100;
boatMass = 3; //kg
boatSpeedMpS = hullEfficiency*waterOutputVolumePerSec*jetOutputSpeedMpS/boatMass;
echo ("estimated boat speed with hull drag", boatSpeedMpS, "[m/s]", boatSpeedMpS*3.6, "[km/h]");
