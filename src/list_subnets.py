#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bittensor Subnet Lister

This script connects to the Bittensor network and lists information
about all available subnets using the DynamicInfo API for Dynamic TAO.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import bittensor as bt
from rich.console import Console
from rich.table import Table
from rich.progress import Progress


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="List Bittensor Subnets")
    parser.add_argument(
        "--endpoint", 
        type=str, 
        default=None,
        help="Custom endpoint for Bittensor network (default: use Bittensor's default)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default=None,
        help="Output file path for saving results (JSON format)"
    )
    parser.add_argument(
        "--network", 
        type=str, 
        default="finney",
        choices=["finney", "local", "test"],
        help="Bittensor network to connect to (default: finney)"
    )
    parser.add_argument(
        "--no-color", 
        action="store_true",
        help="Disable colored output"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Show debug information including errors"
    )
    parser.add_argument(
        "--deep", 
        action="store_true",
        help="Perform deep inspection of emission values"
    )
    return parser.parse_args()


def get_subtensor(endpoint: Optional[str] = None, network: str = "finney") -> bt.subtensor:
    """Initialize and return a subtensor connection."""
    if endpoint:
        return bt.subtensor(network=network, chain_endpoint=endpoint)
    return bt.subtensor(network=network)


def extract_emission_value(obj: Any) -> float:
    """Helper to extract emission value from various object types."""
    if obj is None:
        return 0.0
        
    # If it's a direct number
    if isinstance(obj, (int, float)):
        return float(obj)
        
    # If it's a Bittensor Balance object
    if hasattr(obj, 'tao'):
        return float(obj.tao)
    
    # If it's an object with __float__ method
    try:
        return float(obj)
    except (ValueError, TypeError):
        pass
    
    # If it's an object with specific attributes
    for attr in ['tao', 'value', 'amount', 'rao']:
        if hasattr(obj, attr):
            try:
                return float(getattr(obj, attr))
            except (ValueError, TypeError):
                pass
    
    # If it's a dict
    if isinstance(obj, dict):
        for key in ['tao', 'value', 'amount', 'rao']:
            if key in obj:
                try:
                    return float(obj[key])
                except (ValueError, TypeError):
                    pass
    
    return 0.0


def get_subnet_info(subtensor: bt.subtensor, netuid: int, console: Console, deep_inspection: bool = False) -> Dict[str, Any]:
    """Get detailed information about a specific subnet using DynamicInfo API."""
    result = {
        "netuid": netuid,
        "subnet_name": "Unknown",
        "symbol": "Unknown",
        "validators_count": 0,
        "miners_count": 0,
        "emission_value": 0.0,
        "tempo": 0,
        "last_update": 0,
        "price": 0.0,
        "debug": {},  # To store debug information
        "error": None
    }
    
    try:
        # Get dynamic subnet info
        dynamic_info = None
        try:
            # Try to use the new DynamicInfo API from Dynamic TAO
            dynamic_info = subtensor.subnet(netuid)
            
            if dynamic_info:
                result["subnet_name"] = dynamic_info.subnet_name if hasattr(dynamic_info, 'subnet_name') else "Unknown"
                result["symbol"] = dynamic_info.symbol if hasattr(dynamic_info, 'symbol') else "Unknown"
                result["tempo"] = dynamic_info.tempo if hasattr(dynamic_info, 'tempo') else 0
                
                # Store all attributes for debugging
                if deep_inspection:
                    for attr_name in dir(dynamic_info):
                        if not attr_name.startswith('_') and not callable(getattr(dynamic_info, attr_name)):
                            try:
                                attr_val = getattr(dynamic_info, attr_name)
                                result["debug"][f"dynamic_info.{attr_name}"] = str(attr_val)
                            except Exception:
                                pass
                
                # Get emission value with multiple approaches
                if hasattr(dynamic_info, 'emission'):
                    emission_val = extract_emission_value(dynamic_info.emission)
                    if emission_val > 0:
                        result["emission_value"] = emission_val
                
                # Check for other emission-related attributes
                for emission_attr in ['alpha_in_emission', 'tao_in_emission', 'pending_alpha_emission', 'pending_root_emission']:
                    if hasattr(dynamic_info, emission_attr) and result["emission_value"] == 0.0:
                        emission_val = extract_emission_value(getattr(dynamic_info, emission_attr))
                        if emission_val > 0:
                            result["emission_value"] = emission_val
                            break
                
                result["last_update"] = dynamic_info.last_step if hasattr(dynamic_info, 'last_step') else 0
                
                # Get price information
                if hasattr(dynamic_info, 'price') and hasattr(dynamic_info.price, 'tao'):
                    result["price"] = float(dynamic_info.price.tao)
        except Exception as e:
            if deep_inspection:
                console.print(f"[yellow]Dynamic API error for subnet {netuid}: {str(e)}[/yellow]")
            # If DynamicInfo API fails, we'll still try to get some data via Metagraph
            pass
        
        # Always try to get metagraph data for validators and miners
        try:
            metagraph = bt.metagraph(netuid=netuid, subtensor=subtensor)
            
            # Store all metagraph attributes for debugging
            if deep_inspection:
                for attr_name in dir(metagraph):
                    if not attr_name.startswith('_') and not callable(getattr(metagraph, attr_name)):
                        try:
                            attr_val = getattr(metagraph, attr_name)
                            result["debug"][f"metagraph.{attr_name}"] = str(type(attr_val))
                        except Exception:
                            pass
            
            # Try multiple approaches to get validator count
            if hasattr(metagraph, 'validator_permit'):
                # Count validators with permits
                result["validators_count"] = sum(1 for p in metagraph.validator_permit if p)
            elif hasattr(metagraph, 'validators'):
                # Use validators attribute directly
                result["validators_count"] = len(metagraph.validators)
            elif hasattr(metagraph, 'S') and hasattr(metagraph, 'neurons'):
                # Count neurons with non-zero stake as validators
                result["validators_count"] = sum(1 for s in metagraph.S if s > 0)
            
            if hasattr(metagraph, 'n'):
                # Total number of neurons
                total_neurons = int(metagraph.n)
            elif hasattr(metagraph, 'neurons'):
                total_neurons = len(metagraph.neurons)
            else:
                total_neurons = 0
                
            result["miners_count"] = max(0, total_neurons - result["validators_count"])
            
            # If we couldn't get emission via DynamicInfo, try via metagraph
            if result["emission_value"] == 0.0:
                # Try all possible approaches to get emissions
                if hasattr(metagraph, 'emission'):
                    try:
                        if deep_inspection:
                            console.print(f"[cyan]Subnet {netuid} emission type: {type(metagraph.emission)}[/cyan]")
                        
                        emission = extract_emission_value(metagraph.emission)
                        
                        if emission > 0 and hasattr(metagraph, 'tempo') and metagraph.tempo > 0:
                            # Convert to daily value
                            blocks_per_day = 24 * 60 * 60 / 12  # assume 12 sec block time
                            emission_per_block = emission
                            emission_per_day = emission_per_block * (blocks_per_day / metagraph.tempo)
                            result["emission_value"] = emission_per_day
                    except Exception as e:
                        if deep_inspection:
                            console.print(f"[yellow]Error calculating emission for subnet {netuid}: {str(e)}[/yellow]")
                
                # Also try to get emission information from subtensor
                try:
                    # This method may exist in some Bittensor versions
                    if hasattr(subtensor, 'get_emission_value_by_subnet'):
                        emission = subtensor.get_emission_value_by_subnet(netuid=netuid)
                        result["emission_value"] = extract_emission_value(emission)
                except Exception:
                    pass
                    
                # Try to get emissions via DTAO methods
                try:
                    if deep_inspection and hasattr(subtensor, 'get_subnet_emission_info'):
                        emission_info = subtensor.get_subnet_emission_info(netuid=netuid)
                        result["debug"]["emission_info"] = str(emission_info)
                        if emission_info and hasattr(emission_info, 'emission'):
                            result["emission_value"] = extract_emission_value(emission_info.emission)
                except Exception:
                    pass
                
        except Exception as e:
            if deep_inspection:
                console.print(f"[yellow]Metagraph error for subnet {netuid}: {str(e)}[/yellow]")
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def list_all_subnets(subtensor: bt.subtensor, deep_inspection: bool = False) -> List[Dict[str, Any]]:
    """List all subnets and their information."""
    console = Console()
    
    try:
        # Try to get information for all subnets at once using the DynamicInfo API
        all_subnets_info = []
        try:
            dynamic_infos = subtensor.all_subnets()
            console.print("[green]Successfully retrieved subnet information using DynamicInfo API[/green]")
            
            # Create a nicely formatted progress display
            with Progress() as progress:
                task = progress.add_task("[cyan]Processing subnet data...", total=len(dynamic_infos))
                
                for dynamic_info in dynamic_infos:
                    netuid = dynamic_info.netuid
                    subnet_info = get_subnet_info(subtensor, netuid, console, deep_inspection)
                    all_subnets_info.append(subnet_info)
                    progress.update(task, advance=1)
                    
            return all_subnets_info
            
        except Exception as e:
            console.print(f"[yellow]Could not use DynamicInfo API: {str(e)}[/yellow]")
            
        # Fall back to getting subnets one by one
        total_subnets = subtensor.get_total_subnets()
        console.print(f"[yellow]Falling back to retrieving subnet information one by one. Total subnets: {total_subnets}[/yellow]")
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Processing subnet data...", total=total_subnets)
            
            for netuid in range(total_subnets):
                subnet_info = get_subnet_info(subtensor, netuid, console, deep_inspection)
                all_subnets_info.append(subnet_info)
                progress.update(task, advance=1)
                
        return all_subnets_info
        
    except Exception as e:
        console.print(f"[red]Error getting subnet list: {str(e)}[/red]")
        return []


def get_symbol_representation(symbol: str) -> str:
    """Convert a symbol to a representation that can be displayed in all terminals."""
    if not symbol or symbol == "Unknown":
        return "Unknown"
        
    # Mapping dictionary for special symbols
    symbol_map = {
        # Greek (UTF-8 display generally correct)
        'Τ': 'Τ (T)',  # Tau (Root)
        'α': 'α',  # alpha
        'β': 'β',  # beta
        'γ': 'γ',  # gamma
        'δ': 'δ',  # delta
        'ε': 'ε',  # epsilon
        'ζ': 'ζ',  # zeta
        'η': 'η',  # eta
        'θ': 'θ', # theta
        'ι': 'ι',  # iota
        'κ': 'κ',  # kappa
        'λ': 'λ',  # lambda
        'μ': 'μ',  # mu
        'ν': 'ν',  # nu
        'ξ': 'ξ',  # xi
        'ο': 'ο',  # omicron
        'π': 'π',  # pi
        'ρ': 'ρ',  # rho
        'σ': 'σ',  # sigma
        'τ': 'τ',  # tau
        'υ': 'υ',  # upsilon
        'φ': 'φ', # phi
        'χ': 'χ', # chi
        'ψ': 'ψ', # psi
        'ω': 'ω',  # omega
        
        # Hebrew (potentially problematic)
        'א': 'alef',
        'ב': 'bet',
        'ג': 'gimel',
        'ד': 'dalet',
        'ה': 'he',
        'ו': 'vav',
        'ז': 'zayin',
        'ח': 'het',
        'ט': 'tet',
        'י': 'yod',
        'ך': 'kaf-sofit',
        'כ': 'kaf',
        'ל': 'lamed',
        'ם': 'mem-sofit',
        'מ': 'mem',
        'ן': 'nun-sofit',
        'נ': 'nun',
        'ס': 'samekh',
        'ע': 'ayin',
        'ף': 'pe-sofit',
        'פ': 'pe',
        'ץ': 'tsadi-sofit',
        'צ': 'tsadi',
        'ק': 'qof',
        'ר': 'resh',
        'ש': 'shin',
        'ת': 'tav',
        
        # Arabic (potentially problematic)
        'ا': 'alif',
        'ب': 'ba',
        'ت': 'ta',
        'ث': 'tha',
        'ج': 'jim',
        'ح': 'ha',
        'خ': 'kha',
        'د': 'dal',
        'ذ': 'dhal',
        'ر': 'ra',
        'ز': 'zay',
        'س': 'sin',
        'ش': 'shin',
        'ص': 'sad',
        'ض': 'dad',
        'ط': 'ta',
        'ظ': 'za',
        'ع': 'ayn',
        'غ': 'ghayn',
        'ف': 'fa',
        'ق': 'qaf',
        'ك': 'kaf',
        'ل': 'lam',
        'م': 'mim',
        'ن': 'nun',
        'ه': 'ha',
        'و': 'waw',
        'ي': 'ya',
        'ى': 'alif',
        
        # Other special characters
        'ᚠ': 'fehu',  # Rune
    }
    
    # Check if the symbol is a Hebrew or Arabic character
    if '\u0590' <= symbol <= '\u06FF':  # Unicode range for Hebrew and Arabic
        return symbol_map.get(symbol, symbol)
    
    # For other characters, try to display them normally
    try:
        # Simple encoding test
        symbol.encode('utf-8')
        return symbol
    except UnicodeEncodeError:
        # Fallback in case of problems
        if symbol in symbol_map:
            return symbol_map[symbol]
        else:
            return f"U+{ord(symbol):04X}" if len(symbol) == 1 else "?"


def display_subnets(subnet_data: List[Dict[str, Any]], use_color: bool = True, show_debug: bool = False):
    """Display subnet information in a formatted table."""
    console = Console(highlight=use_color, color_system="auto" if use_color else None)
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Subnet ID")
    table.add_column("Name")
    table.add_column("Symbol")
    table.add_column("Validators")
    table.add_column("Miners")
    table.add_column("Emission (TAO/day)")
    table.add_column("Price")
    
    if show_debug:
        table.add_column("Error")
    
    active_subnets = 0
    
    for subnet in subnet_data:
        # Only show subnets where we at least have some data
        has_data = (
            subnet.get("validators_count", 0) > 0 or 
            subnet.get("miners_count", 0) > 0 or 
            subnet.get("emission_value", 0) > 0 or
            subnet.get("subnet_name", "Unknown") != "Unknown" or
            subnet.get("symbol", "Unknown") != "Unknown"
        )
        
        if has_data or show_debug:
            active_subnets += 1
            
            # Convert symbol with our function
            symbol = get_symbol_representation(subnet.get("symbol", "Unknown"))
            
            row = [
                str(subnet["netuid"]),
                subnet.get("subnet_name", "Unknown"),
                symbol,
                str(subnet.get("validators_count", 0)),
                str(subnet.get("miners_count", 0)),
                f"{subnet.get('emission_value', 0):.6f}",
                f"{subnet.get('price', 0):.6f}"
            ]
            
            if show_debug and "error" in subnet and subnet["error"]:
                row.append(str(subnet["error"]))
            elif show_debug:
                row.append("")
                
            table.add_row(*row)
    
    console.print("\n[bold]Bittensor Subnet Information[/bold]")
    console.print(table)
    console.print(f"\nActive Subnets: {active_subnets} / Total Subnets: {len(subnet_data)}")
    console.print("\nCreated by [bold]Graytensor[/bold] - taotrack.com")


def save_to_file(subnet_data: List[Dict[str, Any]], output_path: str):
    """Save subnet data to a JSON file."""
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_subnets": len(subnet_data),
        "subnets": subnet_data,
        "powered_by": "Graytensor - taotrack.com"
    }
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)


def main():
    """Main function."""
    args = parse_arguments()
    
    try:
        # Initialize subtensor connection
        subtensor = get_subtensor(args.endpoint, args.network)
        
        # Get subnet information
        subnet_data = list_all_subnets(subtensor, args.deep)
        
        # Display subnet information
        display_subnets(subnet_data, not args.no_color, args.debug)
        
        # Save to file if output path is provided
        if args.output:
            save_to_file(subnet_data, args.output)
            print(f"\nData saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 