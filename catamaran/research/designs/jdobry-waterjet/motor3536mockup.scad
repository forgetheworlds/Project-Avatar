
module motor3536mockup()
{
  difference()
  {
    union() {
      cylinder(d=35,h=21.5);
      translate([0,0,22]) rotate([0,0,10]) cylinder(d=35, h=44.5-22);
      translate([0,0,44.5]) rotate([0,0,10]) cylinder(d1=35, d2=19, h=50-44.5);
      translate([0,0,50]) rotate([0,0,10]) cylinder(d=9, h=52.7-50);
      translate([0,0,-25.7]) rotate([0,0,10]) cylinder(d=4, h=79.5);
      translate([0,0,8]) rotate([0,90,0]) cylinder(d=5,h=46,center=true);
      translate([0,0,18.5]) rotate([-90,0,0]) cylinder(d=5,h=30);
      translate([5,0,18.5]) rotate([-90,0,0]) cylinder(d=5,h=30);
      translate([-5,0,18.5]) rotate([-90,0,0]) cylinder(d=5,h=30);
    }
    translate([25/2,0,-0.01]) cylinder(d=M3hole,h=5);
    translate([-25/2,0,-0.01]) cylinder(d=M3hole,h=5);
    translate([0,25/2,-0.01]) cylinder(d=M3hole,h=5);
    translate([0,-25/2,-0.01]) cylinder(d=M3hole,h=5);
    translate([-2,1,-25.7+2.5]) cube(4);
    translate([0,0,8]) rotate([0,90,0]) cylinder(d=2.5,h=50,center=true);
  }
  cylinder(d=18,h=40);
}
