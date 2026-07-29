//****************************************************
//***   home of this project                       ***
//***   https://www.thingiverse.com/thing:2872620  ***
//****************************************************

// library from https://github.com/openscad/scad-utils
use <scad-utils/transformations.scad>
use <scad-utils/shapes.scad>

// library from https://github.com/openscad/list-comprehension-demos
use <skin.scad>

include <motor3536mockup.scad>
include <MG996Rmockup.scad>

//*********************************************************************************************************

fn=32;

wall = 2.5;
thinWall = 0.6;

impellerChamberH = 25;
impellerChamberD = 35;
impellerHubDia = 12;
impellerBlades = 3;
impellerLead = 24;
impellerDirection = -1; // or +1
impellerLen = 19;
impellerRotation = impellerDirection * 120; //impellerDirection * 360 * impellerLen / impellerLead;
impellerCurve = wall*2;
impellerBladePowShape = 1.1;
impellerBladePow = 8;
impellerCurvePow = 0.3;
impellerWall = 3.5;


motorHolderPlus = 30;
holderLen = 60;

r1ab = impellerChamberD / 2;
flange = r1ab + 15;
r2a = 55;
r2b = 40;
th = 2;
motorWall = 5;
Xsize = 110;
Zsize = 25;
starParts = 2; //1; //3;
shaft = 4.2;
shaftCaseD = 9.8;
shaftCaseH = 100;
jetBlades = 3;
M3hole = 3.6;
M3nutDia = 4.8;
M3nutLen = 6.5;
M3headDia = 6; // DIN 912
ballSize = 50;
ballSpace = 0.4;
screwPitch = r1ab+wall+M3nutDia;
jetLen = 30;
jetRudlerLen = 35;
jetMultiplier = 2;
jetOut = r1ab / sqrt(jetMultiplier);
jetOutExtraLen = jetOut;
jetRudlerArmShift = 10;
jetRudlerOut = jetOut+2*wall;

ballOffset = jetLen +ballSize*0.27;

M4nutHex = 7;
M4nutHexOuter = M4nutHex / cos(30);
M4nutHexSpace = M4nutHexOuter + 1;
M4nutHexLenSpace = 5;
bearingHoleD = 7.2; //MR74ZZ
bearingHoleH = 3 + 5; //MR74ZZ + DIN 985 M4 nut

carrierDiameter = 9;
carrierH = 5;
carrierBladeW   = 3;
carrierBladeH   = 3;

keelAngle = 141;

plateX = Xsize+motorHolderPlus-12+20;
plateY = (r1ab+20)*2;
fenceH = 10;

coolingR = r1ab+12;
coolingPipe = 4.2;
coolingPipePitch = 0.8;

ruddlerType = 0; // 0 = doose; 1 = ball
cut = false;
rudlerAngle = 35*cos($t*360);

connection_1_2_nuts = true;

servoBase = jetOut+wall+jetRudlerArmShift-(3+40.1-26.6)+13;

glue = 0.15;

function myShape(r1ab, r2, pos) = 
  [for (i=[0:fn-1]) 
    let (a=i*360/fn)
    let (r=1/(1+10*pow(pos,3)))
    [
      r1ab*sign(cos(a))*pow(abs(cos(a)), r), 
      r2*sign(sin(a))*pow(abs(sin(a)), r)
    ]
  ];
function myStar(r, wall) = 
  [
    [0,-wall/2],
    [r,-wall/2],
    [r,+wall/2],
    [0,+wall/2]
  ]; 
  
  
function myTransform(x1, x2, Zsize, i, myShape, rot=0) = 

  transform (
           translation([Xsize*(i/fn),0,Zsize*cos(180*i/fn)])*
           rotation([0,90+90*i/fn,0])*
           translation([-r1ab,0,0])*
           rotation([0,0,rot]),
           myShape
  );

module cutModule()
{
  if (cut == true) cube ([150,60,60]);  
}
      
module tube(r1ab, r2a, r2b, R, wall=0, e=0)
{
  skin([for(i=[0:fn*0.85])
    let(x1 = wall+r1ab+(r2a-r1ab)*atan(pow(2*(i/fn),1.3))/180)
    let(x2 = wall+r1ab+(r2b-r1ab)*atan(pow(3*(i/fn),1.3))/180)
    myTransform (x1, x2, Zsize, i, myShape(x1, x2, i/fn))
  ]);
}

module way(r1ab, r2a, r2b, R, wall=0, e=0, l)
{
  for(j=[0:starParts-1])
    skin([for(i=[0:fn*3/4-1])
      let(x1 = wall+r1ab+(r2a-r1ab)*pow((i/fn),2))
      let(x2 = wall+r1ab+(r2b-r1ab)*pow((i/fn),2))
      myTransform (x1, x2, Zsize, i, myStar(l,thinWall+(wall-thinWall)*pow(i/fn,1/6)), 180+j*360/starParts)
    ]);
}

module screw_1_2(r1ab, holePos, holes = M3hole)
{
  for (i=[4:8])
    translate ([screwPitch*cos(i*60),screwPitch*sin(i*60),holePos]) 	
			cylinder(d=holes, h=M3nutLen*2-wall/2);
}

module nuts_1_2(r1ab, holePos, case)
{
  for (i=[4:8])
  {
    translate ([screwPitch*cos(i*60),screwPitch*sin(i*60),holePos]) cylinder(d=case, h=M3nutLen*2);
  }
  translate([0,0,-wall]) intersection()
  {
    union () for (i=[0:5])
    {
      rotate([0,0,i*60])
        translate([0,-wall/2,0])
          cube([flange,wall,impellerChamberH]);
    }
    cylinder(r2=flange-wall, r1=r1ab+2*wall, h=impellerChamberH);
  }
}

module keelCutHalf(x,y,w)
{
  angle = (180-keelAngle) / 2;
  rotate([angle,0,0]) translate ([-w/2,-w,-w]) cube([x,y,w]);
}

module keelCut(x,y,w)
{
  translate ([-impellerChamberH,0,-Zsize+0.01])
  {
    plateRound = 2;
    union()
    {
      keelCutHalf(x,y,w);
      mirror([0,1,0]) keelCutHalf(x,y,w);
    }
  }  
}
module plateHalf(plateX,plateY,wall)
{
  angle = (180-keelAngle) / 2;
  deskY = plateY/2;
  rotate([angle,0,0]) cube([plateX,deskY,wall]);
  translate([0,cos(angle)*deskY-wall,sin(angle)*deskY]) cube([plateX,wall,fenceH]);
}

module plate(plateX,plateY,wall)
{
  //translate ([-impellerChamberH,-plateY/2,-Zsize]) cube([plateX,plateY,wall]);

  translate ([-impellerChamberH,0,-Zsize])
  {
    plateRound = 2;
    union()
    {
      plateHalf(plateX,plateY,wall);
      mirror([0,1,0]) plateHalf(plateX,plateY,wall);
    }
  }
}

module base()
{
  difference ()
  {
    union()
    {
      difference()
      {
        union()
        {
          translate ([0,0,-r1ab-Zsize]) tube(r1ab,r2a,r2b,Zsize, wall,e=0);
          rotate([0,-90,0]) difference()
          {
            union()
            {
              translate([0,0,-0.01])cylinder(r=r1ab+wall, h=impellerChamberH+0.01, $fn=fn);
              translate ([0,0,impellerChamberH]) rotate([180,0,0]) cylinder(r=flange, h=wall);
              translate ([0,0,impellerChamberH-wall]) rotate([180,0,0]) cylinder(r1=flange, r2=0, h=wall*4);
              y2 = cos((180-keelAngle)/2)*plateY;
              translate ([-Xsize/2,-y2/2,impellerChamberH-wall]) cube([Xsize/2,y2,wall]);
              translate ([0,coolingR,impellerChamberH-wall]) cylinder(r=coolingPipe+2*wall, h=wall);
              if (connection_1_2_nuts)
                nuts_1_2(r1ab, impellerChamberH-M3nutLen*2,M3nutDia+2*wall);
              else
                translate ([-screwPitch,0,impellerChamberH-M3nutLen*2.5]) cylinder(d=M3nutDia*3, h=M3nutLen*2.5);

            }
            if (connection_1_2_nuts)
            {
              translate([0,0,impellerChamberH+0.1]) rotate([180,0,0]) screw_1_2(r1ab, 0,M3nutDia);
            }
            else
            {
              screw_1_2(r1ab, impellerChamberH-M3nutLen*2.5+wall+1);
              translate ([-screwPitch,0,impellerChamberH-M3nutLen-1]) cylinder(d=M3nutDia, h=M3nutLen*2);
            }
            translate ([0,coolingR,impellerChamberH-5]) cylinder(r=coolingPipe, h=10);
          }
          plate(plateX,plateY,wall);
        }
        translate ([0,0,-r1ab-Zsize]) tube(r1ab,r2a,r2b,Zsize, 0, 1);
				translate ([1,0,0]) rotate([0,-90,0]) cylinder(r=r1ab, h=impellerChamberH+2, $fn=fn);
				translate([-(impellerChamberH-0.5),0,0]) rotate([0,-90,0]) cylinder(r1=r1ab, r2=r1ab+0.5, h=1, $fn=fn);  // elefant foot immunity
      }
      
      div = 0.5;
      //translate ([shaftCaseH*div,0,0]) rotate([0,90,0]) cylinder(d=shaftCaseD+2*wall, h=shaftCaseH*div-10);
      translate ([0,0,0])  rotate([0,90,0]) doose(impellerHubDia/2, (shaftCaseD+2*wall)/2, h=shaftCaseH/* *div */ - 10);
      translate ([0,0,-r1ab-Zsize]) intersection()
      {
        way(r1ab,r2a,r2b,Zsize, wall, l=r2b);
        tube(r1ab,r2a,r2b,Zsize, wall);
        translate ([-impellerChamberH,-plateY/2,r1ab+wall/2]) cube([plateX,plateY,wall+2*Zsize]);
      }
      intersection()
      {
        translate ([0,0,-r1ab-Zsize]) tube(r1ab,r2a,r2b,Zsize, wall);
        pitch = 11;
        translate ([0,0,-Zsize+wall/2])
				let (i=0) 
        union() /*for(i=[-1:+1])*/ translate([0,i*pitch,0])
        {
          rotate([0,90,0]) hull()
          {
            offset = abs(sin((180-keelAngle)/2) * i*pitch);
            translate([-10-0.5-offset,0,0]) cylinder(d=wall/4, h=Xsize*1.3);
            translate([-0.5-offset,0,0]) cylinder(d=wall, h=Xsize*1.3);
          }
        }
      }
    }
    translate ([-0.01,0,0]) rotate([0,90,0]) cylinder(d=shaftCaseD, h=150); // shaft case
    
		translate ([shaftCaseH-20,0,0]) sphere(d=shaftCaseD+1); // for glue to fixate shaft case
    translate ([shaftCaseH-20,0,0]) cylinder(d=shaft, h=shaftCaseD+1); // for glue to fixate shaft case 
  }
}

module mainPart()
{
  difference()
  {
    union()
    {
      base();
    }
    translate ([-impellerChamberH-0.1,-50,-79.999-Zsize]) cube ([200,100,80]);  
    keelCut(plateX*1.2+60, plateY*1.2+60,2*Zsize);
    translate ([-impellerChamberH-0.1,0,0]) cutModule(); 

  }
}

module testPattern()
{
  difference()
  {
    union()
    {
      baseTest();
    }
    translate ([-impellerChamberH-0.1,-50,-79.999-Zsize]) cube ([200,100,80]);  
    keelCut(plateX*1.2+60, plateY*1.2+60,60);
  }
}

function bladeWfunction(pos) = (
//  wall-(wall-1)*pow(pos,impellerCurvePow)
  impellerWall
//   1+(impellerWall-1)*pow(pos,impellerCurvePow)
//   1+(impellerWall-1)*pow(pos,impellerCurvePow)
);


function myStar2(r, curve=5, ww) = 
  [   
    for(i=[0:fn]) 
    ( 
      [r*i/fn,-ww/2+curve*pow(i/fn,impellerBladePow)]
    ),
    for(i=[0:fn]) 
    (
      [r*(fn-i)/fn,+ww/2+curve*pow((fn - i)/fn,impellerBladePow)]
    )
  ]; 

module impBlade(propDia, starParts, impellerLen, totRot=impellerRotation, curve=impellerCurve)
{
  for(j=[0:starParts-1])
  skin([for(i=[0:fn])
    let(rot = totRot*pow((fn-i)/fn,impellerBladePowShape))
    transform (
         translation([0,0,(impellerLen*i/fn)])*
         rotation([0,0,-rot]),
         myStar2(propDia,curve,ww=bladeWfunction(i/fn)), 180+j*360/starParts)
  ]);
}

module jetBlade(propDia, starParts, impellerLen, totRot=100, curve=wall*1.4)
{
  for(j=[0:starParts-1])
  skin([for(i=[0:fn])
    let(rot = totRot*pow(1-i/fn,4))
//    let(wwStep=thinWall+(wall-thinWall)*pow(sin(180*i/fn),1/3))
    let(wwStep=thinWall+(wall-thinWall)*sin(180*i/fn))
    transform (
         translation([0,0,(impellerLen*i/fn)])*
         rotation([0,0,-rot]),
         myStar2(propDia,impellerDirection*wall,curve,ww=wwStep),180+j*360/starParts)
  ]);
}

module impeller()
{
  impellerHubDia = 12;
  propDia = impellerChamberD-1;
  intersection()
  {
    difference()
    {
      intersection()
      {
        union()
        {
          cylinder(d=impellerHubDia, h=impellerLen);
          for (i=[0:impellerBlades])
            rotate([0,0,i*360/impellerBlades])
              impBlade(propDia/2, starParts, impellerLen);
        }
//        cylinder(d=propDia, h=impellerLen);
        skin([for(i=[0:fn]) 
          transform(translation([0,0,i*impellerLen/fn]), circle(impellerHubDia*0.5+(propDia-impellerHubDia)*0.5*(((i/fn)>0.5)?1:pow(sin(i*90/(fn*0.5)),1)), $fn=fn))]);

      }
      // shaft
      translate ([0,0,0]) cylinder(d=shaft,h=impellerLen+1/*-1.2*/);
      // nut space
      //translate([0,0,impellerLen-1]) cylinder(d=M4nutHexSpace, h=impellerLen);

      // carrier space
      translate ([0,0,-1]) cylinder(d=carrierDiameter,h=carrierH+1.01);
      intersection()
      {
        translate ([-carrierBladeW/2,-carrierDiameter,0]) cube([carrierBladeW,carrierDiameter*2,carrierH+carrierBladeH]);
        cylinder(d=carrierDiameter,h=carrierH+carrierBladeH);
      }
    }
    cylinder(d=propDia, h=impellerLen);
  }
}

module doose(r1, r2, h)
{
  avg = (r1+r2) / 2;
  diff = r1 - avg;
  skin([for(i=[0:fn]) 
    transform(translation([0,0,i*h/fn]), circle(avg+diff*cos(i/fn*180), $fn=fn))]);
}

module jet()
{
  difference()
  {
    rotate([0,-90,0])
    union()
    {
      difference()
      {
        pd = coolingPipe+1.5+2*wall;
        zd = pd-1.5;
        union()
        {
          doose(r1=r1ab+wall, r2=jetOut+wall, h=jetLen);        
          cylinder(r=flange, h=wall);
          //difference()
          //{
          //	cylinder(r=r1ab+2.5*wall, h=3*wall);
		      //  translate([0,0,3*wall]) rotate_extrude() translate([r1ab+2.5*wall,0,0]) circle(2*wall);
		      //}

          translate([0,0,wall]) cylinder(r1=flange, r2=0, h=wall*4);
          if (ruddlerType == 1)
          {
            translate([0,0,ballOffset]) sphere(d=ballSize);
          }
          else
          {
            difference()
            {
              union ()
              {
                translate([0,0,jetLen]) cylinder(r=jetOut+wall, h=jetOutExtraLen+0.1, $fn=fn);
                hull()
                {
									translate([jetOut,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([0,90,0]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h = 2*wall);
									translate([jetOut,0,jetLen/2]) rotate([0,90,0]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h = wall);
								}
                hull()
                {
                	translate([-jetOut,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([0,-90,0]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h = 2*wall);
                	translate([-jetOut,0,jetLen/2]) rotate([0,-90,0]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h = wall);
								}
              }
              translate([0,0,jetLen+jetOutExtraLen]) cylinder(r=jetOut+8*wall, h=jetOutExtraLen);
              translate([jetOut+2*wall-M3nutLen,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([0,90,0]) cylinder(d=M3nutDia, h = M3nutLen+1);
              translate([-(jetOut+2*wall-M3nutLen),0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([0,-90,0]) cylinder(d=M3nutDia, h = M3nutLen+1);
            }
          }
          hull()
          {
            translate ([0,coolingR,zd]) sphere(d=pd);
            translate ([0,0,zd]) sphere(d=pd);
          }
          hull()
          {
            translate ([0,coolingR,0]) cylinder(d=pd, h=zd);
            translate ([0,0,0]) cylinder(d=pd, h=zd);
          }
        }
        screw_1_2(r1ab, -1);
        screw_1_2(r1ab, wall, M3headDia);
        translate ([0,coolingR,-1]) render() 
          cylinder(d=coolingPipe, h=pd+1);
        hull()
        {
          translate ([0,coolingR,zd]) sphere(d=coolingPipe+1.5);
          translate ([0,coolingR-5,zd]) sphere(d=coolingPipe+1.5);
        }
        hull()
        {
          translate ([0,r1ab-(coolingPipe+3)/2,coolingPipe/2]) sphere(d=coolingPipe+1.5);
          translate ([0,coolingR-5,zd]) sphere(d=coolingPipe+1.5);
        }
        
        translate ([0,0,-0.01]) doose(r1=r1ab, r2=jetOut, h=jetLen+0.002);
        translate ([0,0,-0.5]) cylinder(r1=r1ab+0.5, r2=r1ab, h=1); // elefant foot immunity
        translate ([0,0,-1]) cylinder(r=jetOut, h=jetLen+ballSize, $fn=fn);
        if (ruddlerType == 1)
        {
          translate ([ballSize/2-M3nutLen, 0, ballOffset]) rotate([0,90,0])  cylinder(d=M3nutDia,h=M3nutLen+1);
          translate ([-(ballSize/2-M3nutLen), 0, ballOffset]) rotate([0,-90,0])  cylinder(d=M3nutDia,h=M3nutLen+1);
        } else {
	        translate([0,0,ballOffset]) hull()
	        {
	          rotate([+20,0,]) cylinder(r=jetOut, h=100);
	          rotate([-20,0,]) cylinder(r=jetOut, h=100);
	        }
	      }

         rotate([0,90,0]) translate ([-150+0.1,0,0]) cutModule();
      }
      impellerHubDia = 12;
      propDia = 19;
      impellerLen = jetLen;
      
      render() intersection()
      {
        difference()
        {
          union()
          {
            cylinder(d=bearingHoleD+2*wall, h=bearingHoleH);
            translate([0,0,bearingHoleH]) cylinder(d1=bearingHoleD+2*wall, d2=1, h=impellerLen);
            for (i=[0:jetBlades])
              rotate([0,0,60+i*360/jetBlades])
                jetBlade(r1ab+wall, starParts, impellerLen, 20, 1.4*wall);
          }
          //translate ([0,0,-1])cylinder(d=M4nutHexSpace,h=M4nutHexLenSpace+1.01);
          translate ([0,0,0]) cylinder(d=bearingHoleD,h=bearingHoleH);
          translate([0,0,-0.5]) cylinder(d1=bearingHoleD+1, d2=bearingHoleD, h=1); // elefant foot immunity
          translate ([0,0,bearingHoleH]) cylinder(d1=bearingHoleD,d2=shaft,h=impellerLen*0.4);
        }
        doose(r1=r1ab+wall/2, r2=jetOut+wall/2, h=impellerLen+M4nutHexLenSpace);
      }
    }
    keelCut(16+20, plateY*1.2+60,20);
    translate ([-150+0.1,0,0]) cutModule();
  }
}

module jetRuddler()
{
  outR1 = jetRudlerOut + wall; 
  difference()
  {
    union()
    {
      difference()
      {
        union()
        { 
          doose(r1=outR1+wall, r2=jetRudlerOut+wall, h=jetRudlerLen);
          translate([0,0,-M3nutDia/2-wall]) cylinder(r=outR1+wall, h=M3nutDia/2+wall, $fn=fn);
        }
        translate([0,0,-0.01]) doose(r1=outR1, r2=jetRudlerOut, h=jetRudlerLen+0.02);
        translate([0,0,-M3nutDia/2-wall-0.01]) cylinder(r=outR1, h=M3nutDia/2+wall+0.02, $fn=fn);
      }
      intersection()
      {
        union()
        {
          translate([jetOut+2*wall,0,0]) rotate([0,90,0]) cylinder(d2=M3nutDia+4*wall, d1=M3nutDia+2*wall, h = 2*wall);
          translate([-(jetOut+2*wall),0,0]) rotate([0,-90,0]) cylinder(d2=M3nutDia+4*wall, d1=M3nutDia+2*wall, h = 2*wall);
        }
        union()
        { 
          doose(r1=outR1+wall, r2=jetRudlerOut+wall, h=jetRudlerLen);
          translate([0,0,-M3nutDia/2-wall]) cylinder(r=outR1+wall, h=M3nutDia/2+wall, $fn=fn);
        }
      }
      rotate([0,90,0]) hull() 
      {
        translate([0,0,outR1-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
        #translate([0,-(M3nutDia+1.5*wall),outR1-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
      }
      rotate([0,90,0]) hull() 
      {
        translate([0,-(M3nutDia+1.5*wall),outR1-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
        translate([0,-jetRudlerArmShift,outR1+jetRudlerArmShift-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
      }
      rotate([0,90,0]) hull() 
      {
        translate([0,-jetRudlerArmShift-20,outR1+jetRudlerArmShift-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
        translate([0,-jetRudlerArmShift,outR1+jetRudlerArmShift-wall]) cylinder(d=M3nutDia+2*wall,h=wall);
      }
    }
    translate([-3*jetRudlerOut,0,0]) rotate([0,90,0]) cylinder (d=M3nutDia,h=6*jetRudlerOut);
    hull()
    {
      rotate([180-45,0,0]) cylinder(r=jetOut+1.5*wall,h=jetRudlerOut*2);
      rotate([180+45,0,0]) cylinder(r=jetOut+1.5*wall,h=jetRudlerOut*2);
    }
    for (i=[1:4])
    rotate([0,90,0]) translate([0,-jetRudlerArmShift-3-i*4,outR1+jetRudlerArmShift-wall-1]) cylinder(d=2,h=2*wall); 
    //#rotate([0,90,0]) translate([0,-jetRudlerArmShift-6*3,outR1+jetRudlerArmShift-wall-1]) cylinder(d=2,h=2*wall); 
  }
  //jetRudlerArmShift    
}

module ballRudler()
{
  inner = ballSize + ballSpace;
  screwDiff = 8;
  armLevel = ballSize/10;
  
  difference()
  {
    union()
    {
      sphere(d=inner+2*wall);
      intersection()
      {
        rotate([0,90,0]) cylinder(d=inner+2*wall, h=20);
        sphere(d=inner+3*wall);
      }
      rotate([0,-90,0]) cylinder (r=jetOut+wall, h=impellerChamberH+15);
      hull()
      {
        translate([0,screwDiff,(inner+2*wall)/2 - armLevel]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h=armLevel+1.5);
        translate([0,-screwDiff,(inner+2*wall)/2 - armLevel]) cylinder(d1=M3nutDia+4*wall, d2=M3nutDia+2*wall, h=armLevel+1.5);
      }
    }
    sphere(d=inner);
    rotate([0,90,0]) cylinder(d=inner, h=100);
    //translate([-200-12,-100,-100]) cube(200);
    rotate([0,-90,0]) cylinder (r=jetOut, h=100);
    hull()
    {
      rotate([0,90,-45]) cylinder(d=40, h=100);
      rotate([0,90,+45]) cylinder(d=40, h=100);
    }
    translate([0,0,-50]) cylinder(d=M3hole, h=100);
    nutLen = 5;
    translate([0,screwDiff,1.5+(inner+2*wall)/2 - nutLen]) cylinder(d=M3nutDia, h=nutLen+1);
    translate([0,-screwDiff,1.5+(inner+2*wall)/2 - nutLen]) cylinder(d=M3nutDia, h=nutLen+1);
  }
}

module rudlerArm()
{
  inner = ballSize + ballSpace;
  screwDiff = 8;
  h = 3*wall;
  difference()
  {
    union()
    {
      hull()
      {
        translate([0,screwDiff,(inner+2*wall)/2 +1.5]) cylinder(d=M3hole+3*wall, h=h);
        translate([0,-screwDiff,(inner+2*wall)/2 +1.5]) cylinder(d=M3hole+3*wall, h=h);
      }
      hull()
      {
        translate([0,screwDiff,(inner+2*wall)/2 +1.5+h]) cylinder(d=M3hole+3*wall, h=wall);
        translate([0,-50,(inner+2*wall)/2 +1.5+h]) cylinder(d=M3hole+3*wall, h=wall);
      }
    }
    for(i=[6:13])
      translate([0,-i*4,(inner+2*wall)/2]) cylinder(d=1.5,h=h*2);
    translate([0,screwDiff,(inner+2*wall)/2]) cylinder(d=M3hole,h=h*2);
    translate([0,-screwDiff,(inner+2*wall)/2]) cylinder(d=M3hole,h=h*2);
    translate([0,0,(inner+2*wall)/2]) cylinder(d=6.5,h=h*2);
  }
}

module motorHolder ()
{
  plus=motorHolderPlus;
  holderDia = 38;
  difference()
  {
    union()
    {
      y2 = cos((180-keelAngle)/2)*plateY;
			x2 = 0.5*plateY*sin((180-keelAngle)/2)+fenceH; 
			hull()
			{
      	translate([plateX,0,-0.01]) rotate([0,-90,0]) cylinder(d=holderDia, h=2*wall);
      	translate([plateX-2*wall,wall-y2/2,-2*Zsize+0.5*plateY*sin((180-keelAngle)/2)+fenceH]) cube([2*wall,y2-2*wall,Zsize]);
      }
    	translate([plateX-2*wall,-y2/2,-2*Zsize+0.5*plateY*sin((180-keelAngle)/2)+fenceH]) cube([2*wall,y2,Zsize]);
      
			hull()
			{
				translate([plateX,y2/2-1.5*wall,-Zsize+x2]) rotate([0,-90,0]) cylinder(d=wall, h=holderLen/2);
				translate([plateX-2*wall,(holderDia-wall)/2*sin(45),(holderDia-wall)/2*cos(45)]) rotate([0,90,0]) cylinder(d=wall, h=2*wall);
			}
			mirror ([0,1,0]) hull()
			{
				translate([plateX,y2/2-1.5*wall,-Zsize+x2]) rotate([0,-90,0]) cylinder(d=wall, h=holderLen/2);
				translate([plateX-2*wall,(holderDia-wall)/2*sin(45),(holderDia-wall)/2*cos(45)]) rotate([0,90,0]) cylinder(d=wall, h=2*wall);
			}
			//translate([0,0,10]) rotate([180-30,0,0]) translate([plateX-holderLen,-wall/2,10]) cube([holderLen,wall,Zsize]);
			//rotate([180+45,0,0]) translate([plateX-holderLen,-wall/2,10]) cube([holderLen,wall,Zsize]);

      translate([plateX+impellerChamberH-holderLen,0,-0.01]) plate(holderLen,plateY,2*wall);
    }
    translate ([0,0,-r1ab-Zsize]) tube(r1ab+0.2,r2a+0.2,r2b+0.2,Zsize, wall,e=0);
    translate([0,0,-0.01]) plate(plateX+0.1,plateY,wall+0.1, wall=wall+glue);
    translate([plateX+10,0,0]) rotate([0,-90,0]) cylinder(d=14, h=20);
    translate([plateX-40,0,-0.01]) keelCut(80+40, plateY*1.2+40,40);
    translate ([60,0,0]) cutModule();
    translate([plateX+10,25/2,0]) rotate([0,-90,0]) cylinder(d=M3hole, h=20);
    translate([plateX+10,-25/2,0]) rotate([0,-90,0]) cylinder(d=M3hole, h=20);
    translate([plateX+10,0,25/2]) rotate([0,-90,0]) cylinder(d=M3hole, h=20);
    translate([plateX+10,0,-25/2]) rotate([0,-90,0]) cylinder(d=M3hole, h=20);
  }
}

module servoHolder()
{ 
  translate([0,0,5]) difference()
  {
    union()
    {
      translate([0,-65-wall,-30]) cube([60,wall+20-0.01,30+servoBase]);
      //translate([wall/2,-65+0.01,-30]) cube([2*wall,40,30+servoBase]);
      translate([0,0,-Zsize]) rotate([keelAngle/2,0,0]) translate([0,0,36]) cube([60,2*wall,servoBase+5]);
    }
    keelCut(plateX*1.2+60, plateY*1.2+60,60);
    render() translate([20,-55,servoBase]) MG996Rmockup(180-rudlerAngle,15);
    translate([20-12,-55-11,servoBase-30]) cube([44,22,40]);
    mainPart();
  }
}

module baringMockup()
{
	rotate([0,-90,0]) difference()
	{
	  cylinder(d=bearingHoleD, h=bearingHoleH);
	  translate([0,0,-1]) cylinder(d=shaft, h=bearingHoleH+2);
	}
}

module demo()
{
  rot = ($t < 1/2) ? [0,-15-30*sin($t*360*2),$t * 360*2] : [($t-0.5) * 360*2, 0, 0];
    
  //rotate(rot)
  {
    color("lightblue") 
       render() mainPart();
    color("Silver") translate ([0,0,0]) rotate([0,90,0]) cylinder(d=shaftCaseD, h=100);

    color("Violet") translate ([-1,0,0]) rotate([0,-90,0]) rotate([0,0,20-$t*360*8]) render() impeller();
    color("Silver") render() translate ([-impellerChamberH-10,0,0]) rotate([0,90,0]) cylinder(d=shaft, h=150);
    color("LightGreen") translate ([-impellerChamberH-wall,0,0]) 
      render() jet();
    color("gold", 0.4) translate ([-impellerChamberH+10,coolingR,0]) rotate([0,-90,0]) difference()
    {
       cylinder(d=5, h=20);
       translate([0,0,-1]) cylinder(d=4, h=22);
    }
    if (ruddlerType == 1)
    { 
      color("LightSalmon") translate ([-impellerChamberH-wall-ballOffset,0,0]) rotate([0,0,35*cos($t*360)]) 
        render() ballRudler();
      color("OrangeRed") translate ([-impellerChamberH-wall-ballOffset,0,0]) rotate([0,0,rudlerAngle]) 
      render() rudlerArm();
    }
    else
    {
      color("LightSalmon") translate ([-impellerChamberH-wall,0,0]) rotate([0,-90,0]) translate([0,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([35,0,0]) jetRuddler();
    }
    color("Thistle")  render() motorHolder();
    //color("Thistle")  render() servoHolder();
    color("Gray",0.4) translate ([-impellerChamberH-wall,0,0]) render() baringMockup();
    color("Gray",0.4) render() translate([plateX+0.02,0,0]) rotate([90,0,90]) motor3536mockup();
    //color("Gray",0.4) render() translate([20,-55,servoBase+5]) MG996Rmockup(180-rudlerAngle);
  }
}

module teardown()
{
  translate ([30,0,0]) color("lightblue") 
     render() mainPart();
  color("Violet") translate ([-1,0,0]) rotate([0,-90,0]) rotate([0,0,20]) render() impeller();
  translate ([-10,0,0]) color("LightGreen") translate ([-impellerChamberH-wall,0,0]) render() jet();
  if (ruddlerType == 1)
  {
    translate ([-55,0,0]) color("LightSalmon") translate ([-impellerChamberH-wall-(impellerChamberH+10),0,0]) rotate([0,0,0]) render() 
      ballRudler();
    translate ([-55,0,20]) color("OrangeRed") translate ([-impellerChamberH-wall-(impellerChamberH+10),0,0]) rotate([0,0,0]) render() rudlerArm();
  }
  else
  {
    color("LightSalmon") translate ([-impellerChamberH-wall-(impellerChamberH+10),0,0]) rotate([0,-90,0]) translate([0,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([0,0,0]) jetRuddler();
  }
  translate ([90,0,0]) color("Thistle")  render() motorHolder();
  //translate ([30,-25,0]) color("Thistle")  render() servoHolder();
}


//motor3536mockup();
//MG996Rmockup(0,15);
//rotate([90-keelAngle/2,0,0]) render () servoHolder();
//cut = false;
//demo();
//translate([0,-110,0]) testPattern();
//motorHolder();
//render() servoHolder();
//translate([0,-2*plateY,0]) 
//  teardown();
//jet();
//rotate([0,-90,0]) translate([0,0,jetLen+jetOutExtraLen-(M3nutDia+2*wall)/2]) rotate([35,0,0])
//  jetRuddler();
//mainPart();
//baseTest();
//color("Violet") plate(plateX,plateY,wall);
//keelCut(plateX*1.2+60, plateY*1.2+60,60);
//impellerCurve = wall; impellerBlades = 3; impellerRotation = 60; impellerCurvePow = 3; impellerBladePow = 3; 
//impellerCurvePow = 1; impellerBladePowShape=1.5; rotate([0,180,0]) 
//impeller();
//ballRudler();
//fn=64; doose(40,20,60);

//rudlerArm();

