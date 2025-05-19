from django.shortcuts import render
from calendar import monthrange

from decimal import Decimal, ROUND_HALF_UP
# Create your views here.
from datetime import datetime
from decimal import *
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.db.models import ExpressionWrapper
from django.http import JsonResponse
from acl.models import *


def chart_data(request):
    data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],  # Example labels (e.g., months)
        'solarGeneration': [50, 75, 60, 80, 90],  # Example solar generation data (kW)
        'hours': ['00:00', '01:00', '02:00', '03:00', '04:00'],  # Example hours
        'inverterOutput': [10, 12, 14, 16, 18],  # Example inverter output data (kW)
        'arrayOutput': [20, 25, 30, 35, 40],  # Example array output data (kW)
    }
    return JsonResponse(data)


def index(request):
    data = {
        'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May'],  # Example labels (e.g., months)
        'solarGeneration': [50, 75, 60, 80, 90],  # Example solar generation data (kW)
        'hours': ['00:00', '01:00', '02:00', '03:00', '04:00'],  # Example hours
        'inverterOutput': [10, 12, 14, 16, 18],  # Example inverter output data (kW)
        'arrayOutput': [20, 25, 30, 35, 40],  # Example array output data (kW)
    }

    if request.method == 'POST':
        charge_rate = request.POST.get('chargeRate')  # Get the value of chargeRate
        if charge_rate:
            try:
                # Convert charge_rate to float for multiplication
                charge_rate = float(charge_rate)

                # Perform the multiplication (charge_rate * 450)
                result = charge_rate * 450

                # Return the result in the response
                return HttpResponse(f"Home Consumption rate multiplied by 450 is: {result} kWh")
            except ValueError:
                return HttpResponse("Invalid input. Please enter a valid number for the charge rate.")
        else:
            return HttpResponse("No charge rate provided.")

    return render(request, 'main.html')


def process_input(request):
    yearly_consumption =Decimal('0.0')
    final_total_sold_energy = Decimal('0.0')
    final_total_sold_energy_price = Decimal('0.0')
    daily_consumption = Decimal('0.0')
    total_import_price_per_day = Decimal('0.0')  # Initialize total import price per day
    total_import_kwh_per_day = Decimal('0.0')  # Initialize total import kWh per day
    total_import_kwh = Decimal('0.0')  # Initialize total import kWh
    total_import_price = Decimal('0.0')  # Initialize total import price
    cumulative_battery_size = 0.0
    consumption_option = "Daily"  # Default to Daily
    monthly_consumptions_per_month = []
    yearly_acl_consumptions_per_month = []
    monthly_consumptions = []  # Initialize monthly consumptions

      # Initialize monthly consumptions per month
    # Initialize input variables
    home_consumption_value = ""
    solar_array_size_value = ""
    month_value = ""
    usage_profile_value = ""
    battery_capacity_value = ""
    yearly_export_price = Decimal('0.0')  # Initialize yearly export price
    table_info = []

    # Yearly percentages and days for each month
    YEARLY_PERCENTAGES = {
        "January": {"days": 31, "percent": 9.29},
        "February": {"days": 28, "percent": 8.45},
        "March": {"days": 31, "percent": 6.60},
        "April": {"days": 30, "percent": 7.45},
        "May": {"days": 31, "percent": 8.03},
        "June": {"days": 30, "percent": 8.67},
        "July": {"days": 31, "percent": 8.95},
        "August": {"days": 31, "percent": 9.56},
        "September": {"days": 30, "percent": 7.45},
        "October": {"days": 31, "percent": 8.29},
        "November": {"days": 30, "percent": 8.52},
        "December": {"days": 31, "percent": 8.74},
    }

    distinct_times = PvElectricity.objects.values_list('time', flat=True).distinct()
    distinct_times = sorted([datetime.strptime(str(time), "%H:%M:%S").strftime("%H:%M") for time in distinct_times])

    # unique_months = PvElectricity().get_unique_months()
     # Define the correct order
    MONTH_ORDER = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # Get unique months from the DB
    db_months = set(PvElectricity.objects.values_list('month', flat=True))

    # Keep only months present in DB, in calendar order
    unique_months = [month for month in MONTH_ORDER if month in db_months]
    distinct_months = sorted(PvElectricity.objects.values_list('month', flat=True).distinct())

    electricity_import_cost = None
    pv_generation_data = []
    daily_pv_generation_data_sum = 0
    monthly_pv_generation_data_sum = 0
    home_consumption = 0
    save_home_consumption = 0
    usage_profile_result_data = []
    get_electricity_data_per_time = []

    yearly_pv_generation_data_sum = 0  # Initialize yearly generation sum
    yearly_import_price = Decimal('0')
    yearly_export_price = Decimal('0')
    year_total_import_kwh = Decimal('0')
    year_total_export_kwh = Decimal('0')
    daily_consumption_for_month = None
    days_in_month = None

    if request.method == "POST":
        # Get input values
        consumption_option = request.POST.get("consumption_option", "Yearly")
        home_consumption_value = request.POST.get("home_consuption", "")
        solar_array_size_value = request.POST.get("solarArraySize", "")
        month_value = request.POST.get("month", "")
        usage_profile_value = request.POST.get("usage_profile", "")
        battery_capacity_value = request.POST.get("battery_capacity", "10.0")  # Default if not provided

        if month_value in YEARLY_PERCENTAGES:
            days_in_month = YEARLY_PERCENTAGES[month_value]["days"]

        try:
            home_consumption = int(home_consumption_value) if home_consumption_value.isdigit() else 0
            solar_array_size = int(solar_array_size_value) if solar_array_size_value.isdigit() else 0
            save_home_consumption = home_consumption / 24  

            # Ensure battery_limit is not zero
            try:
                battery_limit = float(battery_capacity_value)
            except ValueError:
                battery_limit = 10.0  # or your default
            if battery_limit == 0:
                battery_limit = 1.0

            if consumption_option == "Daily":
                # Handle Daily consumption option
                electricity_import_cost = my_function(home_consumption)
                usage_profile_result_data = usage_profile_calculation(
                    usage_profile_value, home_consumption, distinct_times, month_value
                )

            elif consumption_option == "Yearly":
                # Handle Yearly consumption option
                yearly_consumption = home_consumption
                monthly_consumptions = []

                for month, data in YEARLY_PERCENTAGES.items():
                    monthly_consumption = (yearly_consumption * (data["percent"] / 100))
                    daily_consumption = monthly_consumption / data["days"]
                    monthly_consumptions.append({
                        "month": month,
                        "monthly_consumption": round(monthly_consumption, 2),
                        "daily_consumption": round(daily_consumption, 2),
                    })

                # Example: Use the first month's daily consumption for further calculations
                if month_value in YEARLY_PERCENTAGES:
                    daily_consumption = next(
                        (item["daily_consumption"] for item in monthly_consumptions if item["month"] == month_value),
                        0
                    )

                electricity_import_cost = my_function(daily_consumption)
                usage_profile_result_data = usage_profile_calculation(
                    usage_profile_value, daily_consumption, distinct_times, month_value
                )

                if consumption_option == "Yearly" and month_value in YEARLY_PERCENTAGES:
                    yearly_percentage = YEARLY_PERCENTAGES[month_value]["percent"]
                    days_in_month = YEARLY_PERCENTAGES[month_value]["days"]
                    monthly_consumption = (home_consumption * yearly_percentage) / 100
                    daily_consumption_for_month = monthly_consumption / days_in_month

            if "pv_generation" in globals():
                pv_generation_data = list(pv_generation(solar_array_size, month_value))
                daily_pv_generation_data_sum = sum(entry["electricity_generation"] for entry in pv_generation_data if entry["electricity_generation"])
                monthly_pv_generation_data_sum = daily_pv_generation_data_sum * 30

            get_electricity_data_per_time = electricity_data_per_time(month_value, solar_array_size) if "electricity_data_per_time" in globals() else []

            # Calculate yearly PV generation
            for month in [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]:
                monthly_generation = PvElectricity.objects.filter(month=month).aggregate(
                    total_generation=Sum(F('electricity') * solar_array_size)
                )['total_generation'] or 0

                yearly_pv_generation_data_sum += monthly_generation

            # Ensure the year is defined before calculating days_in_month
            year = datetime.now().year  # Use the current year

            # Calculate yearly import/export prices and kWh
            for index, month in enumerate([
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]):
                days_in_month = monthrange(year, index + 1)[1]  # Now 'year' is defined
                monthly_import_kwh = Decimal(total_import_kwh_per_day) * days_in_month
                monthly_export_kwh = Decimal(final_total_sold_energy) * days_in_month
                monthly_import_price = Decimal(my_function(float(monthly_import_kwh)))
                monthly_export_price = Decimal(final_total_sold_energy_price) * days_in_month

                yearly_import_price += monthly_import_price
                yearly_export_price += monthly_export_price
                year_total_import_kwh += monthly_import_kwh
                year_total_export_kwh += monthly_export_kwh

        except ValueError:
            electricity_import_cost = "Invalid input. Please enter valid numbers."

    table_info = [
        {
            "time": entry["time"],
            "electricity": entry["electricity"],
            "home_consumption": next((u["home_consumption"] for u in usage_profile_result_data if u["hour"] == entry["time"]), 0)
        }
        for entry in get_electricity_data_per_time or []
    ]

    # Perform battery calculations and accumulate totals
    total_sold_energy = Decimal('0')
    previous_battery_input = 0
    cumulative_battery_size = 0.0
    for idx, i in enumerate(table_info):
        # Save battery level before this hour
        prev_battery_level = cumulative_battery_size

        # Calculate battery for this hour
        cumulative_battery_size, sold_kw, unsupplied = battery_calculation_per_hour(
            float(i["electricity"]),
            float(i["home_consumption"]),
            battery_size_input=float(battery_limit),
            current_battery_level=float(prev_battery_level)
        )
        i["battery_size"] = round(cumulative_battery_size, 2)

        # Battery input (charge) for this hour is the increase in battery level
        battery_input = max(0, cumulative_battery_size - prev_battery_level)
        i["battery_input"] = round(battery_input, 2)

        # Battery discharge for this hour is the decrease in battery level
        battery_discharge = max(0, prev_battery_level - cumulative_battery_size)
        i["battery_discharge"] = round(battery_discharge, 2)

        sold_kw_decimal = Decimal(sold_kw)
        i["sold_kw"] = sold_kw_decimal.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        export_revenue_decimal = (sold_kw_decimal * Decimal(1000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        i["export_revenue"] = export_revenue_decimal

        if i["electricity"] == 0:
            if i["battery_size"] > 0:
                i["import_kwh"] = Decimal(str(round(i["home_consumption"] - i["battery_size"], 2)))
            else:
                i["import_kwh"] = Decimal(str(round(i["home_consumption"], 2)))
        else:
            i["import_kwh"] = Decimal(str(round(unsupplied, 2)))

        i["import_price"] = Decimal(my_function(float(i["import_kwh"])))

        # After battery_calculation_per_hour
        # If there is no electricity generation and battery input is 0, import_kwh = consumption
        if i["electricity"] == 0 and i["battery_size"] == 0:
            i["import_kwh"] = Decimal(str(round(i["home_consumption"], 2)))

        # Calculate import_kwh for all cases
        import_kwh = Decimal(str(i["home_consumption"])) - Decimal(str(i["electricity"])) - Decimal(str(i["battery_size"]))
        i["import_kwh"] = import_kwh if import_kwh > 0 else Decimal('0.00')
        i["import_kwh"] = i["import_kwh"].quantize(Decimal('0.02'))

        # Now calculate import_price using the final import_kwh
        i["import_price"] = Decimal(my_function(float(i["import_kwh"])))

        total_import_kwh_per_day += i["import_kwh"]
        total_import_price_per_day += i["import_price"]
        total_import_kwh += i["import_kwh"]
        total_import_price += i["import_price"]
        total_sold_energy += sold_kw_decimal

    # Final calculations
    total_sold_energy_multiplied = total_sold_energy * Decimal('1000')
    final_total_sold_energy = total_sold_energy + (Decimal(table_info[-1]["battery_size"]) if table_info else 0)
    final_total_sold_energy_price = (total_sold_energy * Decimal('1000')) + (Decimal(table_info[-1]["battery_size"]) * Decimal('1000') if table_info else 0)
    
    yearly_acl_consumptions_per_month = []
    if consumption_option == "Yearly" and home_consumption:
        yearly_consumption = home_consumption
        for month, data in YEARLY_PERCENTAGES.items():
            monthly_value = (yearly_consumption * (data["percent"] / 100))
            
            yearly_acl_consumptions_per_month.append({
                "month": month,
                "days": data["days"],
                "monthly_consumption": round(monthly_value, 1)
        })
    else:
    # For Daily or if not set, you can fill with zeros or skip
        for month, data in YEARLY_PERCENTAGES.items():
            monthly_consumptions.append({
            "month": month,
            "days": data["days"],
            "monthly_consumption": 0
        })

    monthly_imports = []
    if consumption_option == "Yearly":
        yearly_consumption = home_consumption
        for month, data in YEARLY_PERCENTAGES.items():
            days = data["days"]
            monthly_import_kwh = float(total_import_kwh_per_day) * days if total_import_kwh_per_day else 0
            monthly_import_price = my_function(monthly_import_kwh)
            monthly_export_kwh = float(final_total_sold_energy) * days  # <-- FIX: use days for this month
            monthly_export_price = float(monthly_export_kwh) * 1000  # Calculate export price

            monthly_imports.append({
                "month": month,
                "days": days,
                "import_kwh": round(monthly_import_kwh, 1),
                "import_price": round(monthly_import_price, 2) if monthly_import_price else 0,
                "monthly_export_kwh": round(monthly_export_kwh, 1),
                "monthly_export_price": round(monthly_export_price, 2),  # <-- Add this line
            })
    else:
        for month, data in YEARLY_PERCENTAGES.items():
            monthly_imports.append({
                "month": month,
                "days": data["days"],
                "import_kwh": 0,
                "import_price": 0,
                "monthly_export_kwh": 0,
                "monthly_export_price": 0,
            })

    sum_monthly_imports_total_price = sum(m["import_price"] for m in monthly_imports)
    sum_monthly_imports_total_kwh = sum(m["import_kwh"] for m in monthly_imports)
    sum_monthly_export_kwh = sum(m["monthly_export_kwh"] for m in monthly_imports)
    sum_monthly_total_export_price = sum(m["monthly_export_price"] for m in monthly_imports)

    # Pass data to the template
    return render(request, "index.html", {
        "table_info": table_info,
        "home_consumption": daily_consumption,
        "month_value": month_value,
        "consumption_option": consumption_option,
        "distinct_months": distinct_months,
        "unique_months": unique_months,
        "electricity_import_cost": electricity_import_cost,
        "pv_generation_data": pv_generation_data,
        "daily_pv_generation_data_sum": daily_pv_generation_data_sum,
        "monthly_pv_generation_data_sum": monthly_pv_generation_data_sum,
        "total_import_kwh": total_import_kwh,
        "total_import_price": total_import_price,
        "total_sold_energy": total_sold_energy,
        "final_total_sold_energy": final_total_sold_energy,
        "final_total_sold_energy_price": final_total_sold_energy_price,
        "yearly_pv_generation_data_sum": yearly_pv_generation_data_sum,
        "yearly_import_price": yearly_import_price,
        "yearly_export_price": yearly_export_price,
        "year_total_import_kwh": year_total_import_kwh,
        "year_total_export_kwh": year_total_export_kwh,
        "yearly_consumption": yearly_consumption,
        "daily_consumption_for_month": daily_consumption_for_month,
        "days_in_month": days_in_month,
        "home_consumption_value":home_consumption_value,
        "yearly_acl_consumptions_per_month":yearly_acl_consumptions_per_month,
        "total_import_kwh_per_day":total_import_kwh_per_day,
        "total_import_price_per_day":total_import_price_per_day,
        "monthly_imports": monthly_imports,
        "sum_monthly_imports_total_price": sum_monthly_imports_total_price,
         "battery_capacity_value": battery_capacity_value,
    "usage_profile_value": usage_profile_value,
    "solar_array_size_value": solar_array_size_value,
    "sum_monthly_imports_total_kwh":sum_monthly_imports_total_kwh,
        "sum_monthly_export_kwh": sum_monthly_export_kwh,
        "sum_monthly_total_export_price": sum_monthly_total_export_price,
    })


def analyze_energy(request):
    if request.method == 'POST':
        home_consumption_input = request.POST.get('Home Consumption')
        solar_generation_input = request.POST.get('Solar Generation')
        battery_capacity = request.POST.get('Battery Capacity')
        import_price = request.POST.get('Import Price')
        export_price = request.POST.get('Export Price')
        home_consumption_option = request.POST.get('Home Consumption Option')

        if home_consumption_option == 'Daily':
            try:
                processed_data = process_input(home_consumption_input)
                solar_data = process_input(solar_generation_input)

                battery_result = calculate_battery_storage(processed_data, solar_data, float(battery_capacity))
                import_export_result = calculate_import_export(battery_result, float(import_price), float(export_price))

                context = {
                    'home_consumption': processed_data,
                    'solar_generation': solar_data,
                    'battery_result': battery_result,
                    'import_export_result': import_export_result,
                    'home_consumption_option': home_consumption_option,
                }
                return render(request, 'index.html', context)

            except Exception as e:
                context = {
                    'error': f'Error processing input: {str(e)}',
                }
                return render(request, 'index.html', context)

        elif home_consumption_option == 'Yearly':
            # Placeholder for future Yearly logic
            context = {
                'error': 'Yearly consumption processing is not implemented yet.',
            }
            return render(request, 'index.html', context)

        else:
            context = {
                'error': 'Invalid Home Consumption Option selected.',
            }
            return render(request, 'index.html', context)

    return render(request, 'index.html')




def my_function(kwh: float):
    try:
        kwh = float(kwh)
    except (ValueError, TypeError):
        return 0

    total = 0
    remaining = kwh

    # 0-200 kWh at 600 UZS
    block = min(remaining, 200)
    total += block * 600
    remaining -= block
    if remaining <= 0:
        return total

    # 201-1000 kWh at 1000 UZS
    block = min(remaining, 800)
    total += block * 1000
    remaining -= block
    if remaining <= 0:
        return total

    # 1001-5000 kWh at 1500 UZS
    block = min(remaining, 4000)
    total += block * 1500
    remaining -= block
    if remaining <= 0:
        return total

    # 5001-10000 kWh at 1750 UZS
    block = min(remaining, 5000)
    total += block * 1750
    remaining -= block
    if remaining <= 0:
        return total

    # Above 10000 kWh at 2000 UZS
    total += remaining * 2000

    return total
     

def get_days_in_month(year: int, month: int) -> int:
    """Get the number of days in a given month."""
    return monthrange(year, month)[1]


def pv_generation(value: int, month: str):
    # Filter by the specified month and annotate the electricity generation
    electricity_generation = PvElectricity.objects.filter(month=month) \
        .annotate(
            electricity_generation=ExpressionWrapper(
                Coalesce(Sum(F('electricity') * value), 0), output_field=DecimalField()
            )
        ) \
        .values('month', 'time', 'electricity_generation')

    return electricity_generation






def format_time(time_value):
    """Ensure time is in HH:MM format"""
    if isinstance(time_value, str):
        return time_value[:5]  # Extract first 5 characters (HH:MM)
    elif isinstance(time_value, datetime):
        return time_value.strftime("%H:%M")  # Convert datetime to HH:MM
    return str(time_value)  # Keep as is if already in correct format
from datetime import datetime

def usage_profile_calculation(usage_profile: str, home_consumption: int, distinct_times: list, month_value: str = "") -> list:
    """Calculate energy consumption distribution based on the usage profile."""
    if home_consumption == 0:
        return []

    # Generate a default list of 24 hourly times if distinct_times is not valid
    if len(distinct_times) != 24:
        distinct_times = [f"{hour:02d}:00" for hour in range(24)]
    else:
        # Ensure times are in HH:MM format and sorted
        distinct_times = sorted([datetime.strptime(time, "%H:%M").strftime("%H:%M") for time in distinct_times])

    # Define hourly percentages for the "Standart" profile
    standart_percentages = {
        "January": [1.0, 0.9, 0.9, 0.8, 0.8, 1.0, 3.0, 10.0, 7.5, 6.5, 5.5, 5.0, 4.0, 5.0, 3.5, 2.5, 4.0, 6.0, 6.5, 7.1, 5.5, 5.5, 4.5, 3.0],
        "February": [1.0, 0.9, 0.9, 0.9, 0.9, 1.0, 3.8, 10.8, 7.0, 6.0, 6.2, 5.0, 3.7, 3.0, 4.3, 3.7, 4.3, 6.7, 6.0, 5.8, 4.8, 5.2, 4.8, 3.3],
        "March": [0.9, 0.8, 0.8, 0.7, 0.7, 0.9, 3.5, 10.3, 7.0, 6.3, 6.0, 5.2, 4.1, 4.4, 4.1, 3.2, 4.0, 6.0, 7.0, 6.0, 5.3, 5.3, 4.5, 3.0],
        "April": [0.8, 0.6, 0.5, 0.4, 0.4, 0.8, 5.0, 9.0, 6.2, 6.0, 5.7, 5.0, 4.2, 5.4, 4.2, 3.0, 3.7, 5.7, 7.2, 7.5, 6.0, 5.5, 4.2, 3.0],
        "May": [0.7, 0.5, 0.3, 0.4, 0.3, 0.7, 4.3, 8.7, 6.3, 6.1, 5.6, 4.8, 4.9, 5.2, 5.0, 4.4, 4.6, 6.0, 7.2, 6.1, 5.3, 5.6, 4.5, 2.5],
        "June": [0.6, 0.4, 0.3, 0.2, 1.3, 1.6, 3.9, 7.3, 6.0, 5.7, 5.4, 4.7, 4.9, 6.0, 4.8, 5.2, 4.9, 5.4, 7.0, 5.9, 4.7, 6.5, 4.9, 2.4],
        "July": [0.6, 0.4, 0.3, 0.2, 1.3, 1.6, 3.9, 7.3, 6.0, 5.7, 5.4, 4.7, 3.9, 6.1, 5.0, 5.2, 5.2, 5.3, 7.0, 6.4, 4.7, 6.5, 4.9, 2.4],
        "August": [0.7, 0.5, 0.4, 0.3, 0.7, 0.8, 4.4, 7.6, 6.3, 6.0, 5.7, 5.0, 4.2, 5.2, 5.0, 4.9, 3.6, 5.5, 7.2, 6.1, 5.8, 6.6, 5.0, 2.5],
        "September": [0.8, 0.6, 0.5, 0.4, 0.5, 0.8, 4.5, 8.0, 6.5, 6.2, 5.9, 5.2, 5.3, 5.8, 4.2, 4.0, 3.8, 5.6, 7.3, 6.2, 5.0, 5.8, 4.4, 2.7],
        "October": [0.9, 0.7, 0.6, 0.5, 0.6, 0.9, 4.7, 8.3, 6.7, 5.9, 5.6, 5.4, 4.5, 5.5, 4.4, 3.2, 4.0, 5.3, 7.5, 6.4, 5.1, 6.0, 4.4, 2.9],
        "November": [1.0, 0.8, 0.7, 0.6, 0.7, 1.0, 5.0, 8.5, 6.9, 5.5, 5.3, 4.6, 4.6, 5.7, 4.6, 3.4, 4.2, 5.5, 7.5, 6.3, 5.2, 6.2, 4.2, 2.0],
        "December": [1.0, 0.9, 0.8, 0.7, 0.8, 1.0, 5.2, 8.7, 6.0, 5.7, 5.5, 5.8, 4.3, 5.9, 4.8, 2.6, 3.4, 5.2, 6.9, 6.3, 5.1, 5.4, 4.8, 3.2]
    }

    if usage_profile == "Standart":
        # If the submitted month value is not a valid key for Standart, default to "January"
        if (month_value not in standart_percentages):
            month_value = "January"
        percentages = standart_percentages.get(month_value)
        if len(percentages) != 24:
            raise ValueError(f"Invalid number of percentages for {month_value}. Expected 24, got {len(percentages)}.")
        if len(distinct_times) != 24:
            raise ValueError(f"Invalid number of distinct times. Expected 24, got {len(distinct_times)}.")

        # Calculate hourly consumption using the percentages
        return [{
            "hour": hour,
            "home_consumption": round((percentages[index] / 100) * home_consumption, 2),
            "percentage": f"{percentages[index]}%"
        } for index, hour in enumerate(distinct_times)]

    # (The rest of the profile handling remains unchanged.)
    morning_evening_percentages = {
        "00:00": 0, "01:00": 0, "02:00": 0, "03:00": 0, "04:00": 0, "05:00": 0,
        "06:00": 1.6, "07:00": 4, "08:00": 7, "09:00": 8, "10:00": 7, "11:00": 4,
        "12:00": 3, "13:00": 3, "14:00": 4, "15:00": 6.6, "16:00": 12.2, "17:00": 13.6,
        "18:00": 12.2, "19:00": 6.6, "20:00": 3.6, "21:00": 2, "22:00": 1, "23:00": 0.6
    }
    evening_percentages = {
        "00:00": 0, "01:00": 0, "02:00": 0, "03:00": 0, "04:00": 0, "05:00": 0,
        "06:00": 0, "07:00": 0, "08:00": 0, "09:00": 0, "10:00": 0, "11:00": 0,
        "12:00": 0, "13:00": 0, "14:00": 0, "15:00": 0, "16:00": 0.8, "17:00": 4.4,
        "18:00": 11.4, "19:00": 21, "20:00": 23.6, "21:00": 21, "22:00": 11.4, "23:00": 6.2
    }
    morning_afternoon_evening_percentages = {
        "00:00": 0, "01:00": 0, "02:00": 0, "03:00": 0, "04:00": 0, "05:00": 0,
        "06:00": 1.2, "07:00": 3.4, "08:00": 6, "09:00": 6.8, "10:00": 6, "11:00": 6,
        "12:00": 6.4, "13:00": 6.8, "14:00": 6.4, "15:00": 6.4, "16:00": 10.4, "17:00": 11.6,
        "18:00": 10.4, "19:00": 5.6, "20:00": 3, "21:00": 1.8, "22:00": 0.8, "23:00": 0.4
    }

    if usage_profile == "Flat":
        hourly_consumption = home_consumption / 24
        return [{
            "hour": hour,
            "home_consumption": round(hourly_consumption, 2),
            "percentage": "4.17%"
        } for hour in distinct_times]

    if usage_profile == "Mainly Morning and Evening":
        percentages = morning_evening_percentages
    elif usage_profile == "Mainly Evening":
        percentages = evening_percentages
    elif usage_profile == "Morning, Afternoon, and Evening":
        percentages = morning_afternoon_evening_percentages
    else:
        # Fallback to "Flat" if no valid profile is given
        return usage_profile_calculation("Flat", home_consumption, distinct_times)

    return [{
        "hour": hour,
        "home_consumption": round((percentages.get(hour, 0) / 100) * home_consumption, 2),
        "percentage": f"{percentages.get(hour, 0)}%"
    } for hour in distinct_times]

def electricity_data_per_time(month: str, solar_array_size: int):
    """Retrieve electricity data per time for a given month."""
    results = PvElectricity.objects.filter(month=month).values('month', 'time', 'electricity')

    data = []
    for result in results:
        electricity_value = result.get('electricity', 0) or 0  # Ensure no None values
        data.append({
            "month": result["month"],
            "time": result["time"].strftime('%H:%M'),
            "electricity": electricity_value * solar_array_size
        })

    return data


def battery_calculation_per_hour(electricity, home_consumption, battery_size_input=10.0, current_battery_level=0.0):
    # Convert inputs to float
    electricity = float(electricity)
    home_consumption = float(home_consumption)
    
    net = electricity - home_consumption  # surplus if positive, deficit if negative
    
    if net >= 0:
        # Battery can be charged with part of the surplus
        capacity_remaining = battery_size_input - current_battery_level
        charge = min(net, capacity_remaining)
        new_battery_level = current_battery_level + charge
        # Sold kW is any remaining surplus that couldn't be stored
        sold_kw = net - charge
        unsupplied = 0
    else:
        # When there's a deficit, try to cover with a battery discharge
        discharge = min(current_battery_level, abs(net))
        new_battery_level = current_battery_level - discharge
        # In deficit, no energy is sold (or optionally, you could sell remaining unsupplied energy)
        sold_kw = 0
        unsupplied = abs(net) - discharge

    return new_battery_level, sold_kw, unsupplied