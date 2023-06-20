

// https://github.com/adafruit/Adafruit_BMP280_Library/t

#include <Adafruit_BMP280.h>

#undef BMP280_ADDRESS
#define BMP280_ADDRESS 0x76

Adafruit_BMP280 bmp; // I2C Interface

static const float CALIBRAGE = 1009.5;

void setup()
{
  Serial.begin(9600);
  Serial.print(F("BMP280 logger"));
  Serial.print(F(" calibrage="));
  Serial.print(CALIBRAGE);
  Serial.println();

  if (!bmp.begin(BMP280_ADDRESS))
  {
    Serial.println(F("Could not find a valid BMP280 sensor, check wiring!"));
    while (1)
      delay(1000);
  }

  pinMode(LED_BUILTIN, OUTPUT);

  /* Default settings from datasheet.  */
  bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,     /* Operating Mode. */
                  Adafruit_BMP280::SAMPLING_X2,     /* Temp. oversampling */
                  Adafruit_BMP280::SAMPLING_X16,    /* Pressure oversampling */
                  Adafruit_BMP280::FILTER_X16,      /* Filtering. */
                  Adafruit_BMP280::STANDBY_MS_500); /* Standby time. */

  bmp.getTemperatureSensor()->printSensorDetails();
  bmp.getPressureSensor()->printSensorDetails();
}

void loop()
{
  digitalWrite(LED_BUILTIN, HIGH);

  Serial.print(micros() / 1000000.0);
  Serial.print(";");

  Serial.print(bmp.readTemperature());
  Serial.print(";");

  Serial.print(bmp.readPressure());
  Serial.print(";");

  // Serial.print(";");
  // Serial.print(bmp.readAltitude(CALIBRAGE));

  Serial.println();

  digitalWrite(LED_BUILTIN, LOW);

  delay(1 * 1000UL);
}
