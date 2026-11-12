#include <ApplicationServices/ApplicationServices.h>
#include <stdlib.h>
int main(int argc,char**argv){
  double x=atof(argv[1]), y=atof(argv[2]);
  CGPoint p=CGPointMake(x,y);
  CGEventRef mv=CGEventCreateMouseEvent(NULL,kCGEventMouseMoved,p,kCGMouseButtonLeft); CGEventPost(kCGHIDEventTap,mv); CFRelease(mv);
  usleep(100000);
  CGEventRef dn=CGEventCreateMouseEvent(NULL,kCGEventLeftMouseDown,p,kCGMouseButtonLeft); CGEventPost(kCGHIDEventTap,dn); CFRelease(dn);
  usleep(80000);
  CGEventRef up=CGEventCreateMouseEvent(NULL,kCGEventLeftMouseUp,p,kCGMouseButtonLeft); CGEventPost(kCGHIDEventTap,up); CFRelease(up);
  printf("clicked %.0f,%.0f\n",x,y); return 0;
}
