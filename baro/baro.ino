/* This code is to use with Adafruit BMP280           (Metric)
 * It  measures both temperature and pressure and it displays them on the Serial monitor  with the altitude
 * It's a modified version of the Adafruit example code
 * Refer to www.surtrtech.com or SurtrTech Youtube channel
 */

#include <Adafruit_BMP280.h>

#define BMP280_ADDRESS 0x76

Adafruit_BMP280 bmp; // I2C Interface

void setup()
{
  Serial.begin(9600);
  Serial.println(F("BMP280 test"));

  if (!bmp.begin(BMP280_ADDRESS))
  {
    Serial.println(F("Could not find a valid BMP280 sensor,  check wiring!"));
    while (1)
      ;
  }

  /* Default settings from datasheet.  */
  bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,     /* Operating Mode. */
                  Adafruit_BMP280::SAMPLING_X2,     /* Temp. oversampling */
                  Adafruit_BMP280::SAMPLING_X16,    /* Pressure oversampling */
                  Adafruit_BMP280::FILTER_X16,      /* Filtering. */
                  Adafruit_BMP280::STANDBY_MS_500); /* Standby time. */
}

void loop()
{
  Serial.print(micros() / 1000000.0);
  Serial.print(";");

  Serial.print(bmp.readTemperature());
  Serial.print(";");

  Serial.print(bmp.readPressure());
  Serial.print(";");

  // Serial.print(F("Approx altitude = "));
  Serial.print(bmp.readAltitude(1013.00));
  // Serial.println("  m");

  Serial.println();
  delay(500);
}
