module MG996Rmockup(angle=0, screw = 0)
{
  translate([0,0,-26.6]) difference()
  {
    union()
    {
      translate([-10,-10,0]) cube([40.3,20,37]);
      cylinder(d=20,h=40.1);
      cylinder(d=5,h=40.1+4);
      translate([-10-(54-40.3)/2,-10,26.6]) cube([54,20,2]);
    }
    translate([-10-(48-40.3)/2,5,26]) cylinder(d=M3hole,h=4);
    translate([-10-(48-40.3)/2,-5,26]) cylinder(d=M3hole,h=4);
    translate([-10-(48-40.3)/2+48,5,26]) cylinder(d=M3hole,h=4);
    translate([-10-(48-40.3)/2+48,-5,26]) cylinder(d=M3hole,h=4);
  }
  
  rotate([0,0,angle]) translate([0,0,40.1-26.6])
  {
    cylinder(d=8,h=3);
    difference()
    {
      translate([0,0,3]) hull()
      {
        cylinder(d=8,h=1);
        translate([0,-40,0]) cylinder(d=4,h=1);
      }
      for (i=[3:13]) translate([0,-i*3,0]) cylinder(d=2,h=5);
      //#translate([0,-15-18,0]) cylinder(d=2,h=5);
    }
    
  }
  if (screw > 0)
  {
    translate([-10-(48-40.3)/2,5,-screw+2.01]) cylinder(d=2.4,h=screw);
    translate([-10-(48-40.3)/2,-5,-screw+2.01]) cylinder(d=2.4,h=screw);
    translate([-10-(48-40.3)/2+48,5,-screw+2.01]) cylinder(d=2.4,h=screw);
    translate([-10-(48-40.3)/2+48,-5,-screw+2.01]) cylinder(d=2.4,h=screw);
    translate([-10-(48-40.3)/2,5,2.01]) cylinder(d=5,h=3);
    translate([-10-(48-40.3)/2,-5,2.01]) cylinder(d=5,h=3);
    translate([-10-(48-40.3)/2+48,5,2.01]) cylinder(d=5,h=3);
    translate([-10-(48-40.3)/2+48,-5,2.01]) cylinder(d=5,h=3);
  }
}
