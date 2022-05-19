// udp.rs

use chrono::{DateTime, Local, TimeZone};
use etherparse::{SlicedPacket, TransportSlice};
use pcap_parser::pcapng::Block;
use pcap_parser::{create_reader, PcapBlockOwned, PcapError};
use std::fs::File;
use std::path::PathBuf;
use std::str;
use structopt::StructOpt;

#[derive(StructOpt)]
#[structopt(name = "udp", about = "An example of StructOpt usage.")]
struct Opt {
    /// UDP port
    #[structopt(short = "p", long = "port", default_value = "1456")]
    port: u16,

    /// Input file
    #[structopt(parse(from_os_str))]
    input: PathBuf,
}

fn main() {
    let opt = Opt::from_args();

    let file = File::open(opt.input).expect("File open failed");
    let mut reader = create_reader(65536, file).unwrap();

    loop {
        match reader.next() {
            Ok((offset, block)) => {
                // println!("got new block {:?} {:?}", offset, 1);

                match block {
                    PcapBlockOwned::NG(Block::EnhancedPacket(epb)) => {
                        // println!("got new epb {:?}", epb.data);

                        let epb_ts = u64::from(epb.ts_high) << 32 | u64::from(epb.ts_low);
                        let ts_sec = epb_ts / 1_000_000;
                        let ts_nanosec = 1000 * (epb_ts % 1_000_000);

                        #[allow(clippy::cast_possible_wrap)]
                        #[allow(clippy::cast_possible_truncation)]
                        let dt: DateTime<Local> = Local.timestamp(ts_sec as i64, ts_nanosec as u32);

                        let timestamp = dt.format("%Y-%m-%dT%H:%M:%S%.6f");

                        //slice the packet into the different header components
                        let sliced_packet = SlicedPacket::from_ethernet(epb.data);

                        //print some informations about the sliced packet
                        match sliced_packet {
                            Err(value) => println!("Err {:?}", value),
                            Ok(value) => {
                                //  use crate::InternetSlice::*;
                                use crate::TransportSlice::Udp;

                                // match value.ip {
                                //     Some(Ipv4(_ip_header, _extensions)) => {
                                //         println!(
                                //             "  Ipv4 {:?} => {:?}",
                                //             _ip_header.source_addr(),
                                //             _ip_header.destination_addr()
                                //         );
                                //     }
                                //     _ => {}
                                // }

                                if let Some(Udp(udp_header)) = value.transport {
                                    // println!(
                                    //     "  UDP {:?} -> {:?} length {}",
                                    //     udp_header.source_port(),
                                    //     udp_header.destination_port(),
                                    //     udp_header.length() - 8
                                    // );
                                    if udp_header.source_port() == opt.port {
                                        let payload =
                                            &value.payload[0..(udp_header.length() - 8) as usize];
                                        let nmea = str::from_utf8(payload).unwrap();

                                        nmea.lines().for_each(|line| {
                                            println!("{} {}", timestamp, line);
                                        });
                                    }
                                }
                            }
                        }

                        // println!();
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
