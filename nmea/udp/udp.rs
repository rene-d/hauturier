// udp.rs

use etherparse::*;
use pcap_parser::pcapng::*;
use pcap_parser::*;
use std::fs::File;
use std::str;

fn main() {
    let path = "../nmea2.pcap";

    let file = File::open(path).expect("File open failed");
    let mut reader = create_reader(65536, file).unwrap();

    loop {
        match reader.next() {
            Ok((offset, block)) => {
                // println!("got new block {:?} {:?}", offset, 1);

                match block {
                    PcapBlockOwned::NG(Block::EnhancedPacket(epb)) => {
                        // println!("got new epb {:?}", epb.data);

                        //slice the packet into the different header components
                        let sliced_packet = SlicedPacket::from_ethernet(&epb.data);

                        //print some informations about the sliced packet
                        match sliced_packet {
                            Err(value) => println!("Err {:?}", value),
                            Ok(value) => {
                                use crate::InternetSlice::*;
                                use crate::TransportSlice::*;

                                match value.ip {
                                    Some(Ipv4(ip_header, _extensions)) => {
                                        println!(
                                            "  Ipv4 {:?} => {:?}",
                                            ip_header.source_addr(),
                                            ip_header.destination_addr()
                                        );
                                    }
                                    _ => {}
                                }

                                match value.transport {
                                    Some(Udp(udp_header)) => {
                                        println!(
                                            "  UDP {:?} -> {:?} length {}",
                                            udp_header.source_port(),
                                            udp_header.destination_port(),
                                            udp_header.length() - 8
                                        );
                                        if udp_header.source_port() == 1456 {
                                            let payload = &value.payload
                                                [0..(udp_header.length() - 8) as usize];
                                            let nmea = str::from_utf8(&payload).unwrap();

                                            nmea.lines().for_each(|line| {
                                                println!("  nmea {}", line);
                                            });
                                        }
                                    }
                                    _ => {}
                                }
                            }
                        }

                        println!();
                    }
                    PcapBlockOwned::NG(_) => (),
                    PcapBlockOwned::LegacyHeader(_) | PcapBlockOwned::Legacy(_) => {
                        panic!("unexpected Legacy data")
                    }
                }

                reader.consume(offset);
            }
            Err(PcapError::Eof) => break,
            Err(PcapError::Incomplete) => {
                reader.refill().unwrap();
            }
            Err(e) => panic!("error while reading: {:?}", e),
        }
    }
}
