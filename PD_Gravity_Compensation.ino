#include <SPI.h>
#include <Ucglib.h>
#include <AccelStepper.h>
#include <Encoder.h>

// Definir parametros del motor y el driver con la libreria AccelStepper
const int dirPin = 42;
const int stepPin = 43;
AccelStepper stepper(1, stepPin, dirPin);

// Definir parametros del encoder
#define encoderPinA 6
#define encoderPinB 7
int encPosAng = 0;
Encoder encoder(encoderPinA, encoderPinB);
const int maxSpeedLimit = 10000.0;



enum Estado {
  ESPERANDO_SELECCION,
  CONTROL_EXBBA

};

Estado estadoActual = ESPERANDO_SELECCION;


float l1 = 0.5;     // longitud total del eslabón (m)
float lc1 = 0.25;   // distancia al centro de masa (m)
float m1 = 2.0;      // masa (kg)
float g = 9.806;     // gravedad (m/s^2)


///////////// Variables Globales Generales ///////////// 
float value = 0;
float kpd =220.45;     // Ganancia proporcional
float kpi = 0.00;   // Ganancia integral
float kpdd = 7.75;    // Ganancia derivativa
int x = 0;
unsigned long t;
unsigned long t_prev = 0;
volatile unsigned long count = 0;
unsigned long count_prev = 0;
int dt;
int dir = 0;
float Vmax = 5000.0;
float Vmin = -5000.0;
double input = 0;
double output = 0;
const int twoPiRad = 360;
double setpoint = 0;
float ref = 0;
float V = 0;
float nV = 0;
float e, e_prev = 0, pk, pk_prev = 0;
float eint = 0;
float wk, qk;
const int targetTolerance = 2;
//////////////////////////////////////////////////////////
const int interruptorPin = 22;
volatile bool emergencia = false;
const int ledESTOP = 23;
const int ledNONSTOP = 26;
const int finCarA = 44;
const int finCarB = 45;
int startPos = 0;
int startConversion = 0;
unsigned long previousMillis = 0; //Tiempo anterior
unsigned long currentMillis = 0;//Tiempo Actual
unsigned long samplingInterval = 1; //Intervalo del tiempo de muestreo
Ucglib_ST7735_18x128x160_HWSPI ucg(/*cd=*/ 9, /*cs=*/ 10, /*reset=*/ 8);

// Pines de control del menú
const int PIN_ARRIBA = 2;
const int PIN_ABAJO = 3;
const int PIN_SELECCIONAR = 24;

int readEncoder() {
  return encoder.read();
}

int opcionSeleccionada = 0;
int totalOpciones = 3;
bool pantallaActualizada = true;

int gradValSup = 0;
int gradValInf = 0;
int limSup = 0;
int limInf =0;

void buscarLimiteSuperior() {
  stepper.setSpeed(10000);
  stepper.setAcceleration(2500);

  stepper.moveTo(100000); 
  while (stepper.distanceToGo() != 0) {
    limSup = readEncoder();
    gradValSup = map(limSup, -3500, 3500, -360, 360);
    stepper.runSpeed();
    if (digitalRead(finCarA) == LOW) {
      stepper.setCurrentPosition(gradValSup);
            Serial.println(gradValSup);

      break;
    }
    mostrarValorEncoder("Posicion:", gradValSup);
  }

}

int posEXBBX = 64;
int posEXBBY = 70;

void introEXBB(){


 while(true){
  ucg.setColor(0, 0, 0); 
  ucg.setFont(ucg_font_ncenR14_tr);



      ucg.setColor(255,255,255);
      delay(500);
      ucg.setPrintPos(posEXBBX-40, posEXBBY+5);
      ucg.print("EXBB-01");
      
  ucg.setColor(255,255,255);
ucg.drawCircle(posEXBBX, posEXBBY,55, UCG_DRAW_ALL);
  ucg.setColor(255,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,65, UCG_DRAW_ALL);
  ucg.setColor(0,0,255);
ucg.drawCircle(posEXBBX, posEXBBY,75, UCG_DRAW_ALL);
      ucg.setColor(255,0,0);
      
  ucg.setColor(255,255,255);
ucg.drawCircle(posEXBBX, posEXBBY,85, UCG_DRAW_ALL);
  ucg.setColor(255,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,95, UCG_DRAW_ALL);
  ucg.setColor(0,0,255);
ucg.drawCircle(posEXBBX, posEXBBY,105, UCG_DRAW_ALL);

delay(1000);
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,105, UCG_DRAW_ALL);
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,95, UCG_DRAW_ALL);
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,85, UCG_DRAW_ALL);      
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,75, UCG_DRAW_ALL);
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,65, UCG_DRAW_ALL);
  ucg.setColor(0,0,0);
ucg.drawCircle(posEXBBX, posEXBBY,55, UCG_DRAW_ALL);


      ucg.setColor(255,0,0);
      ucg.setPrintPos(posEXBBX-40, posEXBBY+5);
      ucg.print("EXBB-01");
            ucg.setColor(255,255,0);
      ucg.setPrintPos(posEXBBX-40, posEXBBY+5);
      ucg.print("EXBB-01");
            ucg.setColor(0,0,255);
      ucg.setPrintPos(posEXBBX-40, posEXBBY+5);
      ucg.print("EXBB-01");
            ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-40, posEXBBY+5);
      ucg.print("EXBB-01");
      delay(3000);
break;
 }
  }

void commentWaitToPos(){
   ucg.setColor(0, 0, 0); 
  ucg.setFont(ucg_font_ncenR14_tr);



      ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY);
      ucg.print("Inicializando");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+17);
      ucg.print("identificacion");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+34);
      ucg.print("de limites");
      delay(4000);
      
}



void buscarLimiteInferior() {
  stepper.setSpeed(10000);
  stepper.setAcceleration(500);

  stepper.moveTo(-100000); 
  while (stepper.distanceToGo() != 0) {
    limInf = readEncoder();
    gradValInf = map(limInf, -3500, 3500, -360, 360);
    stepper.runSpeed();
    if (digitalRead(finCarB) == LOW) {
      stepper.setCurrentPosition(gradValInf);
            Serial.println(gradValInf);

      break;
      
    }
    mostrarValorEncoder("Posicion:", gradValInf);
  }

}

void moveToStartPosition(){
  stepper.setSpeed(10000);
  stepper.setAcceleration(1050);
 stepper.moveTo(100000);
while(stepper.distanceToGo() !=0){
    startConversion = readEncoder();
    startPos = map(startConversion, -3500, 3500, -360, 360);
     stepper.runSpeed();
    if(startPos >= 11){
     stepper.setCurrentPosition(startPos);
      break;
    }
      mostrarValorEncoder("INICIO", startPos);
      //Serial.println(startPos);

    }

}



int posicionXSTR = 35;
int posicionYSTR = 40;
int valorEncoderAnterior = 0;
int posicionXValorEncoder = 60; // Posición X donde se muestra el valor del encoder
int posicionYValorEncoder = 100; // Posición Y donde se muestra el valor del encoder
bool primerValor = true;

void mostrarValorEncoder(String mensaje, int valorEncoder) {
  ucg.setColor(0, 0, 0); // Color negro para borrar el valor anterior
  ucg.setFont(ucg_font_ncenR12_tr);

 

      
     // Obtener el ancho del texto del valor anterior

  // Si es la primera vez o hay un cambio en el valor, actualiza la pantalla
  if (primerValor || valorEncoder != valorEncoderAnterior) {
    primerValor = false; // Ya no es el primer valor

    // Convertir el entero a String
    String valorAnteriorStr = String(valorEncoderAnterior);
    const char* valorAnteriorChar = valorAnteriorStr.c_str();
  ucg.setColor(255,0,255);

ucg.drawBox(posicionXSTR-20, posicionYSTR-20,100,30);
      ucg.setColor(255,255,255);
      ucg.setPrintPos(posicionXSTR, posicionYSTR);
      ucg.print(mensaje);

     
    ucg_int_t anchoTexto = ucg.getStrWidth(valorAnteriorChar);

    // Borrar solo el espacio donde se muestra el número anterior
    ucg.setColor(255, 255, 255);
    ucg.drawDisc(posicionXValorEncoder+4, posicionYValorEncoder - 6, 20, UCG_DRAW_ALL);

    // Mostrar el nuevo valor del encoder en la posición especificada
    ucg.setColor(0, 0, 0);
    ucg.setPrintPos(posicionXValorEncoder-4, posicionYValorEncoder);
    ucg.print(valorEncoder);
    valorEncoderAnterior = valorEncoder; // Actualizar el valor anterior
  }
}

void upperLimbPositionningText(){
   ucg.setColor(0, 0, 0); 
  ucg.setFont(ucg_font_ncenR12_tr);


while(true){
      ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY-35);
      ucg.print("Proceda a ");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY-17);
      ucg.print("introducir");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+1);
      ucg.print("el brazo,");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+19);
      ucg.print("presione el ");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+37);
      ucg.print("boton 'select' ");
       ucg.setColor(255,255,255);
      ucg.setPrintPos(posEXBBX-55, posEXBBY+55);
      ucg.print("al finalizar.");

      if (digitalRead(PIN_SELECCIONAR) == LOW){
        delay(10);
        break;
      }
}
      delay(10);
}









void controlEXBBA(){

  

  if (digitalRead(interruptorPin) == LOW) { 
    Serial.println("¡Paro de emergencia activado!"); 
    digitalWrite(ledESTOP, HIGH);
    digitalWrite(ledNONSTOP, LOW);
    estadoActual = ESPERANDO_SELECCION;
    // = true;
  }
  else{
        digitalWrite(ledESTOP, LOW);
    digitalWrite(ledNONSTOP, HIGH);
    // = false;
    }
  

   int encoderValue = readEncoder();
 float angle = ((gradValSup/2)-15) * sin((PI / 180) * ((micros() / 20000))) + ((gradValSup/2)+5);  
 encPosAng = map(encoderValue, -3500, 3500, -360, 360);
//  potValue = analogRead(potPin);
//    setpoint = map(potValue, 0, 500, -360, 360);
    input = encPosAng;
    ref = angle;
    
//
//  if(encPosAng >= 360){
//    stepper.stop();
//    
//  }
//  else{
//        stepper.setSpeed(-2500);
//  stepper.run();
//  }


  currentMillis = micros();

  if (currentMillis - previousMillis >= samplingInterval) {
    unsigned long samplingTime = currentMillis - previousMillis;

//    double filteredInput = applyLowPassFilter(encPosAng);
    double deltaT = static_cast<double>(samplingTime) / 1000000.0; 
//    double angularVelocity = (filteredInput - prevFilteredInput) / deltaT;
//    prevFilteredInput = filteredInput;
   // dt = (currentMillis - t_prev);
     // Error de posición
  e = ref - input;  

  // Error de velocidad (derivada del error)
  float dedt = (e - e_prev) / deltaT;

  // ----------------------------
  // Compensación gravitacional
  // ----------------------------
  float q_rad = input * PI / 180.0;  // convertir ángulo medido a radianes
  float G = m1 * lc1 * g * sin(q_rad);

  // Ley de control: PD + G
  V = kpd * e + kpdd * dedt + G;

  // Saturación de voltaje
  if (V > Vmax) {
    V = Vmax;
  }   
  if (V < Vmin) {
    V = Vmin;
  }

  // Aplicar al motor
  stepper.setSpeed(V);
  stepper.runSpeed();

  // Debug
  Serial.print(encPosAng);
  Serial.print(",");
  Serial.println(ref);

  // Guardar estados anteriores
  previousMillis = currentMillis;
  e_prev = e;

   }

        stepper.setSpeed(V);
        stepper.runSpeed(); 

        

//    if ((ref - input) > targetTolerance) {
//      if (ref >= input) {
//        stepper.setSpeed(-V);
//        stepper.runSpeed(); 
//      } else if (ref < input ) {
//        stepper.setSpeed(V);
//        stepper.runSpeed(); 
//      }
////      }else{}
////        stepper.stop();
////      }
//    }
// 
//  Serial.println(-V);
//// Serial.print(", ");
 Serial.print(encPosAng);
  Serial.print(","); 
////  Serial.print(V);
////  Serial.print(",");
  Serial.println(ref);
////  Serial.print(", ");
//// Serial.println(angularVelocity);

previousMillis = currentMillis;
    pk_prev = pk;
    e_prev = e;
  }



void setup() {
  delay(100);
  Serial.begin(115200);
  ucg.begin(UCG_FONT_MODE_TRANSPARENT);
  ucg.setRotate180();
      ucg.clearScreen();

  pinMode(PIN_ARRIBA, INPUT_PULLUP);
  pinMode(PIN_ABAJO, INPUT_PULLUP);
  pinMode(PIN_SELECCIONAR, INPUT_PULLUP);
  pinMode(interruptorPin, INPUT_PULLUP);
  pinMode(ledESTOP, OUTPUT);
  pinMode(ledNONSTOP, OUTPUT);
   pinMode(finCarA, INPUT_PULLUP);
  pinMode(finCarB, INPUT_PULLUP);
  stepper.setMaxSpeed(10000);
  stepper.setAcceleration(1050);
  introEXBB();
  delay(1000);
  ucg.clearScreen();
  commentWaitToPos();
  delay(800);
  ucg.clearScreen();
  delay(100);
  buscarLimiteSuperior();
  delay(100); 
  buscarLimiteInferior();
  delay(2000);
  moveToStartPosition();
  delay(500);
  ucg.clearScreen();
  upperLimbPositionningText();
delay(10);
    ucg.clearScreen();

      previousMillis = micros();
}

void loop() {
  switch (estadoActual) {
    case ESPERANDO_SELECCION:
if (digitalRead(PIN_ARRIBA) == LOW) {
    delay(10); // Debounce
    opcionSeleccionada = (opcionSeleccionada - 1 + totalOpciones) % totalOpciones;
    pantallaActualizada = true;
  }

else if(Serial.available() > 0){
  char command = Serial.read();
  if(command == 'u'){
    delay(10);
    opcionSeleccionada = (opcionSeleccionada-1+totalOpciones)%totalOpciones;
    pantallaActualizada = true;
  }
  else if (command == 't'){
          delay(10);
          switch (opcionSeleccionada) {
            case 0:
              estadoActual = CONTROL_EXBBA;
            break;
        }
  }
}

  if (digitalRead(PIN_ABAJO) == LOW) {
    delay(10); // Debounce
    opcionSeleccionada = (opcionSeleccionada + 1) % totalOpciones;
    pantallaActualizada = true;
  }
      if (digitalRead(PIN_SELECCIONAR) == LOW) {
        delay(10); // Debounce
        switch (opcionSeleccionada) {
          case 0:
            estadoActual = CONTROL_EXBBA;
            break;
        }
      }
        
        
      
      break;


    case CONTROL_EXBBA:
      while (estadoActual == CONTROL_EXBBA) {
        // Lógica para el estado CONTROL_EXBBA
        controlEXBBA();

        // Verificar botón de emergencia y cambiar estado si es necesario
        if (digitalRead(interruptorPin) == LOW) {
          estadoActual = ESPERANDO_SELECCION;
          digitalWrite(ledESTOP, HIGH);
    digitalWrite(ledNONSTOP, LOW);
          break; // Salir del bucle while y volver al menú principal
        }
        
        // Verificar botón de selección y cambiar estado si es necesario
        if (digitalRead(PIN_SELECCIONAR) == LOW) {
          delay(10); // Debounce
          estadoActual = ESPERANDO_SELECCION;
          break; // Salir del bucle while y volver al menú principal
        }
      }
      break;
  }

if (pantallaActualizada) {
    ucg.setFont(ucg_font_ncenR12_tr);
    // ucg.clearScreen(); Para la actualización completa de la pantalla, descomenta esta línea

    // Dibuja las opciones del menú
    for (int i = 0; i < totalOpciones; i++) {
      ucg.setPrintPos(20, 50 + i * 30);
      if (i == opcionSeleccionada) {
        ucg.setColor(255, 0, 255); // Opción seleccionada en rojo
      } else {
        ucg.setColor(255, 255, 255); // Otras opciones en blanco
      }
      ucg.print("Velocidad " + String(i + 1));
    }

    pantallaActualizada = false;
  }

  delay(10); // Pequeña pausa para evitar la detección múltiple del pulsador
}
