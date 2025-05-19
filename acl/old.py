def my_function(text: float):
    try:
        text = float(text)  # Ensure input is an integer
    except (ValueError, TypeError):
        return "Invalid input. Please enter a valid number."

    if text <= 200.0:
        return text * 450.0
    elif text <= 1000.0:
        return 200.0 * 450.0 + (text - 200.0) * 900.0
    elif text <= 5000:
        return 200 * 450 + 800 * 900 + (text - 1000) * 1350
    elif text <= 10000:
        return 200 * 450 + 800 * 900 + 4000 * 1350 + (text - 5000) * 1575
    else:
        return 200 * 450 + 800 * 900 + 4000 * 1350 + 5000 * 1575 + (text - 10000) * 1800
    



def process_input(request):
    daily_consumption= Decimal('0.0')
    total_import_price_per_day = Decimal('0.0')  # Initialize total import price per day
    total_import_kwh_per_day = Decimal('0.0')  # Initialize total import kWh per day
    total_import_kwh = Decimal('0.0')  # Initialize total import kWh
    total_import_price = Decimal('0.0')  # Initialize total import price
    cumulative_battery_size = 0.0
    consumption_option =" "

    # Initialize input variables with empty strings
    home_consumption_value = ""
    solar_array_size_value = ""
    month_value = ""
    usage_profile_value = ""
    battery_capacity_value = ""
    yearly_export_price = Decimal('0.0')  # Initialize yearly export price

    # Initialize solar_array_size with a default value
    solar_array_size = 0

    distinct_times = PvElectricity.objects.values_list('time', flat=True).distinct()
    distinct_times = sorted([datetime.strptime(str(time), "%H:%M:%S").strftime("%H:%M") for time in distinct_times])

    unique_months = PvElectricity().get_unique_months()
    distinct_months = sorted(PvElectricity.objects.values_list('month', flat=True).distinct())

    electricity_import_cost = None
    pv_generation_data = []
    daily_pv_generation_data_sum = 0
    monthly_pv_generation_data_sum = 0
    home_consumption = 0
    save_home_consumption = 0
    usage_profile_result_data = []
    get_electricity_data_per_time = []

    if request.method == "POST":
        consumption_option = request.POST.get("consumption_option", "Daily")
        home_consumption_value = request.POST.get("home_consuption", "")
        solar_array_size_value = request.POST.get("solarArraySize", "")
        month_value = request.POST.get("month", "")
        usage_profile_value = request.POST.get("usage_profile", "")
        battery_capacity_value = request.POST.get("battery_capacity", "10.0")  # default if not provided
    
    if consumption_option == "Daily":
        try:
            home_consumption = int(home_consumption_value) if home_consumption_value.isdigit() else 0
            solar_array_size = int(solar_array_size_value) if solar_array_size_value.isdigit() else 0
            save_home_consumption = home_consumption / 24  

            # Ensure battery_limit is not zero
            try:
                battery_limit = float(battery_capacity_value)
            except ValueError:
                battery_limit = 10.0  # Default value if input is invalid

            # Prevent division by zero
            if battery_limit == 0:
                battery_limit = 1.0  # Set a minimum value to avoid division by zero


            battery_limit = min(battery_limit, solar_array_size)
             # Handle Daily or Yearly consumption option
            
                # Calculate daily consumption for the selected month
            
            electricity_import_cost = my_function(home_consumption)
            usage_profile_result_data = usage_profile_calculation(usage_profile_value, home_consumption, distinct_times, month_value)

            if "pv_generation" in globals():
                pv_generation_data = list(pv_generation(solar_array_size, month_value))
                daily_pv_generation_data_sum = sum(entry["electricity_generation"] for entry in pv_generation_data if entry["electricity_generation"])
                monthly_pv_generation_data_sum = daily_pv_generation_data_sum * 30

            get_electricity_data_per_time = electricity_data_per_time(month_value, solar_array_size) if "electricity_data_per_time" in globals() else []

            # Get the year and month from the request or use the current year
            year = datetime.now().year
            month_number = datetime.strptime(month_value, "%B").month  # Convert month name to number

            # Get the number of days in the selected month
            days_in_month = get_days_in_month(year, month_number)

            # Calculate monthly PV generation using the actual number of days
            monthly_pv_generation_data_sum = daily_pv_generation_data_sum * days_in_month

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


    total_sold_energy = Decimal('0')  # Initialize total_sold_energy

    for i in table_info:
        cumulative_battery_size, sold_kw, unsupplied = battery_calculation_per_hour(
            i["electricity"],
            i["home_consumption"],
            battery_size_input=battery_limit,  # User-provided battery capacity
            current_battery_level=cumulative_battery_size
        )
        i["battery_size"] = round(cumulative_battery_size, 2)
        sold_kw_decimal = Decimal(sold_kw)
        i["sold_kw"] = sold_kw_decimal.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        export_revenue_decimal = (sold_kw_decimal * Decimal(1000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        i["export_revenue"] = export_revenue_decimal

        # Add unsupplied energy (import kWh) to the row
        i["import_kwh"] = Decimal(str(round(unsupplied, 2)))

        # Calculate the import price using my_function
        i["import_price"] = Decimal(my_function(float(i["import_kwh"])))

        # Accumulate totals
        total_import_kwh_per_day += i["import_kwh"]
        total_import_price_per_day += i["import_price"]

        total_import_kwh += i["import_kwh"]
        total_import_price += i["import_price"]

        total_sold_energy += sold_kw_decimal  # Accumulate sold_kw

    # Ensure the last index's sold_kw and export_revenue are synchronized
    if table_info:
        last_index = table_info[-1]
        last_index["sold_kw"] += Decimal(last_index["battery_size"])
        last_index["sold_kw"] = last_index["sold_kw"].quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        # Set export_revenue for the last index based on sold_kw * 1000
        last_index["export_revenue"] = (last_index["sold_kw"] * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    # After calculating total_sold_energy:
    total_sold_energy_multiplied = total_sold_energy * Decimal('1000')

    # Calculate export info
    for i in table_info:
        i["export_info"] = round(i["battery_size"])

    final_export_info = table_info[-1]["export_info"] if table_info else 0.0

    # After your loop that accumulates sold energy:
    total_sold_energy = sum(Decimal(i["sold_kw"]) for i in table_info)

    # Example: Find the battery charge at 23:00 (if available)
    battery_charge_2300 = Decimal('0')
    for i in table_info:
        if i["time"] == "23:00":
            # For instance, suppose i["battery_size"] holds the battery charge at that time
            battery_charge_2300 = Decimal(i["battery_size"])
            break

    # Multiply the battery charge by 1000 and add to total sold energy.
    final_total_sold_energy = total_sold_energy + (battery_charge_2300 )
    final_total_sold_energy_price = (total_sold_energy *Decimal('1000')) + (battery_charge_2300 * Decimal('1000') ) 

    battery_percentage = 0  # Initialize battery percentage

    if table_info:
        last_index = table_info[-1]  # Get the last row
        # Calculate battery percentage safely
        if battery_limit > 0:
            battery_percentage = (Decimal(last_index["battery_size"]) / Decimal(battery_limit)) * 100
            battery_percentage = round(battery_percentage, 2)  # Round to 2 decimal places
        else:
            battery_percentage = 0  # Set to 0 if battery_limit is invalid

    # Example percentages for each month
    percentages = [
        9.29, 8.45, 6.60, 7.45, 8.03, 8.67, 8.95, 9.56, 7.45, 8.29, 8.52, 8.74
    ]

    # Get the current year
    year = datetime.now().year

    # Prepare a list of months, days, and calculated values
    months_and_days = []
    for index, month in enumerate([
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]):
        percentage = percentages[index]
        days = monthrange(year, index + 1)[1]
        calculated_value = 0
        daily_value = 0

        # Calculate the value if home_consumption is provided
        if home_consumption > 0:
            calculated_value = (home_consumption * (percentage / 100))
            daily_value = calculated_value / days  # Calculate daily value

        months_and_days.append({
            "month": month,
            "days": days,
            "percentage": f"{percentage}%",
            "calculated_value": round(calculated_value, 2),
            "daily_value": round(daily_value, 4)  # Add daily value
        })

    # Normalize month names in months_and_days
    for item in months_and_days:
        item["month"] = item["month"].capitalize()  # Ensure consistent capitalization

    # Hourly percentages for each month
    hourly_percentages = {
        "January": [1.0, 0.9, 0.8, 0.8, 0.8, 3.5, 10.0, 7.5, 6.5, 5.5, 5.0, 5.0, 4.9, 5.0, 5.0, 3.8, 4.2, 6.0, 6.5, 5.5, 5.5, 4.5, 3.0, 1.0],
        "February": [1.0, 0.9, 0.8, 0.8, 0.8, 3.5, 9.5, 7.0, 6.2, 5.5, 5.0, 5.0, 4.9, 5.0, 4.8, 3.8, 4.0, 6.7, 6.0, 5.5, 5.5, 5.0, 3.2, 1.0],
        "March": [1.0, 0.9, 0.8, 0.8, 0.8, 3.4, 9.5, 7.0, 6.0, 5.2, 5.0, 5.0, 5.0, 4.8, 4.6, 3.7, 3.9, 6.5, 5.9, 5.5, 5.5, 4.9, 3.0, 1.0],
        "April": [0.9, 0.8, 0.8, 0.8, 0.8, 3.5, 9.3, 7.0, 6.1, 5.4, 4.9, 5.0, 4.8, 4.7, 4.6, 3.6, 3.8, 6.6, 6.1, 5.5, 5.4, 4.9, 3.0, 1.0],
        "May": [0.7, 0.8, 0.8, 0.8, 0.7, 3.5, 9.1, 8.3, 7.1, 6.1, 5.6, 5.3, 5.0, 5.0, 4.9, 4.7, 4.6, 7.2, 6.7, 6.3, 6.1, 5.5, 3.5, 1.0],
        "June": [0.7, 0.8, 0.8, 0.7, 0.7, 3.5, 9.3, 8.4, 7.2, 6.5, 5.7, 5.5, 5.2, 5.0, 5.0, 4.8, 4.5, 7.5, 6.8, 6.5, 6.1, 5.5, 3.4, 1.0],
        "July": [0.8, 0.8, 0.8, 0.7, 0.7, 3.6, 9.2, 8.7, 7.8, 6.3, 5.5, 5.4, 5.2, 5.1, 4.9, 4.6, 4.4, 7.8, 7.1, 6.6, 6.4, 5.6, 3.5, 1.0],
        "August": [0.8, 0.8, 0.8, 0.7, 0.7, 3.6, 9.3, 8.7, 7.6, 6.0, 5.3, 5.2, 5.2, 5.1, 4.9, 4.6, 4.5, 7.7, 7.2, 6.4, 6.1, 5.6, 3.4, 1.0],
        "September": [0.8, 0.8, 0.8, 0.7, 0.7, 3.5, 9.0, 8.6, 7.7, 6.2, 5.5, 5.3, 5.2, 5.2, 5.0, 4.9, 4.6, 7.8, 7.2, 6.4, 6.1, 5.8, 3.5, 1.0],
        "October": [0.9, 0.7, 0.7, 0.7, 0.7, 3.4, 9.1, 8.8, 7.5, 6.0, 5.3, 5.2, 5.1, 5.0, 4.8, 4.5, 4.4, 7.6, 7.0, 6.2, 6.0, 5.5, 3.2, 1.0],
        "November": [0.9, 0.8, 0.8, 0.8, 0.8, 3.5, 9.0, 8.5, 7.5, 6.0, 5.5, 5.3, 5.2, 5.0, 4.8, 4.5, 4.4, 7.5, 7.0, 6.2, 6.0, 5.5, 3.2, 1.0],
        "December": [1.0, 1.0, 1.0, 1.0, 1.0, 3.5, 10.0, 7.5, 6.5, 5.5, 5.0, 5.0, 4.9, 5.0, 5.0, 3.8, 4.2, 6.0, 6.5, 5.5, 5.5, 4.5, 3.0, 1.0]
    }

    hourly_consumption_data = []

    for hour in range(24):
        hour_data = {"hour": f"{hour}:00"}
        for item in months_and_days:
            month = item["month"]
            daily_value = item["daily_value"]
            percentage = hourly_percentages[month][hour]
            hourly_value = daily_value * (percentage / 100)
            hour_data[month] = round(hourly_value, 2)  # Precalculate hourly consumption
        hourly_consumption_data.append(hour_data)

    # Calculate yearly PV generation using actual database values
    yearly_pv_generation_data_sum = 0  # Initialize yearly generation sum

    for month in [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]:
        # Query the database for the total electricity generation for the month
        monthly_generation = PvElectricity.objects.filter(month=month).aggregate(
            total_generation=Sum(F('electricity') * solar_array_size)
        )['total_generation'] or 0

        # Multiply by the number of days in the month
        days_in_month = monthrange(year, datetime.strptime(month, "%B").month)[1]
        yearly_pv_generation_data_sum += monthly_generation * days_in_month

    # Calculate yearly import price
    yearly_import_price = total_import_price  # Use the already calculated total import price

    # Initialize yearly import price
    yearly_import_price = Decimal('0')

    # List of months
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # Iterate over each month
    sum_export_price_breakdown = [] 
    sum_import_price_breakdown = []  # Initialize an empty list to store monthly import kWh
    import_price_breakdown = []  # To store monthly breakdown

    for index, month in enumerate(months):
        # Get the number of days in the month
        days_in_month = monthrange(year, index + 1)[1]

        # Calculate the total import (kWh) for the month
        monthly_import_kwh = Decimal(total_import_kwh_per_day) * days_in_month  # Replace with actual calculation
        monthly_export_kwh = Decimal(final_total_sold_energy) * days_in_month
        # Calculate the import price using `my_function`
        monthly_import_price = Decimal(my_function(float(monthly_import_kwh)))
        monthly_export_price = Decimal(final_total_sold_energy_price) * days_in_month

        # Add to yearly total
        yearly_import_price += monthly_import_price
        yearly_export_price += monthly_export_price


        # Append to breakdown
        import_price_breakdown.append({
            "month": month,
            "days": days_in_month,
            "import_kwh": monthly_import_kwh,
            "import_price": monthly_import_price,
            "monthly_export_kwh":monthly_export_kwh,
            "monthly_export_price": monthly_export_price
        })

        # Append the monthly import kWh to the list
        sum_import_price_breakdown.append(monthly_import_kwh)
        sum_export_price_breakdown.append(monthly_export_kwh)
    # Calculate the total import kWh
    year_total_import_kwh = sum(sum_import_price_breakdown)
    year_total_export_kwh = sum(sum_export_price_breakdown)  # Total import kWh for the year

    # Pass data to the template
    return render(request, "index.html", {
        "electricity_import_cost": electricity_import_cost,
        "pv_generation_data": pv_generation_data,
        "daily_pv_generation_data_sum": daily_pv_generation_data_sum,
        "distinct_months": distinct_months,
        "distinct_times": distinct_times,
        "get_electricity_data_per_time": get_electricity_data_per_time,
        "unique_months": unique_months,
        "monthly_pv_generation_data_sum": monthly_pv_generation_data_sum,
        "home_consumption": home_consumption,
        "save_home_consumption": save_home_consumption,
        "usage_profile_result_data": usage_profile_result_data,
        "table_info": table_info,
        "final_export_info": final_export_info,
        # Pass the input values back for persistence
        "home_consumption_value": home_consumption_value,
        "solar_array_size_value": solar_array_size_value,
        "month_value": month_value,
        "usage_profile_value": usage_profile_value,
        "battery_capacity_value": battery_capacity_value,
        "total_sold_energy": total_sold_energy,  # Original sold energy sum (kW)
        "total_sold_energy_multiplied": total_sold_energy_multiplied,
        "final_total_sold_energy": final_total_sold_energy,
        "final_total_sold_energy_price": final_total_sold_energy_price,  # Final calculation
        "total_import_kwh": total_import_kwh,  # Pass the total import kWh
        "total_import_price": total_import_price,  # Pass the total import price
        "battery_percentage": battery_percentage,  # Pass the battery percentage
        "months_and_days": months_and_days,  # Pass months, days, and calculated values to the template
        "hourly_percentages": hourly_percentages,  # Pass hourly percentages to the template
        "hourly_consumption_data": hourly_consumption_data,  # Pass hourly consumption data to the template
        "yearly_pv_generation_data_sum": yearly_pv_generation_data_sum,  # Pass yearly PV generation sum to the template
        "yearly_import_price": yearly_import_price,  # Pass yearly import price to the template
        "import_price_breakdown": import_price_breakdown,
        "sum_import_price_breakdown": sum_import_price_breakdown,  # Pass the sum of import price breakdown to the template
        "total_import_price_per_day":total_import_price_per_day, 
        "total_import_kwh_per_day":total_import_kwh_per_day ,
        "year_total_import_kwh":year_total_import_kwh,  
        "yearly_export_price":yearly_export_price,
        "year_total_export_kwh":year_total_export_kwh
        
        
    })

#processss input    




def process_input(request):
    daily_consumption= Decimal('0.0')
    total_import_price_per_day = Decimal('0.0')  # Initialize total import price per day
    total_import_kwh_per_day = Decimal('0.0')  # Initialize total import kWh per day
    total_import_kwh = Decimal('0.0')  # Initialize total import kWh
    total_import_price = Decimal('0.0')  # Initialize total import price
    cumulative_battery_size = 0.0
    consumption_option =" "

    # Initialize input variables with empty strings
    home_consumption_value = ""
    solar_array_size_value = ""
    month_value = ""
    usage_profile_value = ""
    battery_capacity_value = ""
    yearly_export_price = Decimal('0.0')  # Initialize yearly export price

    # Initialize solar_array_size with a default value
    solar_array_size = 0

    distinct_times = PvElectricity.objects.values_list('time', flat=True).distinct()
    distinct_times = sorted([datetime.strptime(str(time), "%H:%M:%S").strftime("%H:%M") for time in distinct_times])

    unique_months = PvElectricity().get_unique_months()
    distinct_months = sorted(PvElectricity.objects.values_list('month', flat=True).distinct())

    electricity_import_cost = None
    pv_generation_data = []
    daily_pv_generation_data_sum = 0
    monthly_pv_generation_data_sum = 0
    home_consumption = 0
    save_home_consumption = 0
    usage_profile_result_data = []
    get_electricity_data_per_time = []

    if request.method == "POST":
        consumption_option = request.POST.get("consumption_option", "Daily")
        home_consumption_value = request.POST.get("home_consuption", "")
        solar_array_size_value = request.POST.get("solarArraySize", "")
        month_value = request.POST.get("month", "")
        usage_profile_value = request.POST.get("usage_profile", "")
        battery_capacity_value = request.POST.get("battery_capacity", "10.0")  # default if not provided
    
    if consumption_option == "Daily":
        try:
            home_consumption = int(home_consumption_value) if home_consumption_value.isdigit() else 0
            solar_array_size = int(solar_array_size_value) if solar_array_size_value.isdigit() else 0
            save_home_consumption = home_consumption / 24  

            # Ensure battery_limit is not zero
            try:
                battery_limit = float(battery_capacity_value)
            except ValueError:
                battery_limit = 10.0  # Default value if input is invalid

            # Prevent division by zero
            if battery_limit == 0:
                battery_limit = 1.0  # Set a minimum value to avoid division by zero


            battery_limit = min(battery_limit, solar_array_size)
             # Handle Daily or Yearly consumption option
            
                # Calculate daily consumption for the selected month
            
            electricity_import_cost = my_function(home_consumption)
            usage_profile_result_data = usage_profile_calculation(usage_profile_value, home_consumption, distinct_times, month_value)

            if "pv_generation" in globals():
                pv_generation_data = list(pv_generation(solar_array_size, month_value))
                daily_pv_generation_data_sum = sum(entry["electricity_generation"] for entry in pv_generation_data if entry["electricity_generation"])
                monthly_pv_generation_data_sum = daily_pv_generation_data_sum * 30

            get_electricity_data_per_time = electricity_data_per_time(month_value, solar_array_size) if "electricity_data_per_time" in globals() else []

            # Get the year and month from the request or use the current year
            year = datetime.now().year
            month_number = datetime.strptime(month_value, "%B").month  # Convert month name to number

            # Get the number of days in the selected month
            days_in_month = get_days_in_month(year, month_number)

            # Calculate monthly PV generation using the actual number of days
            monthly_pv_generation_data_sum = daily_pv_generation_data_sum * days_in_month

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


    total_sold_energy = Decimal('0')  # Initialize total_sold_energy

    for i in table_info:
        cumulative_battery_size, sold_kw, unsupplied = battery_calculation_per_hour(
            i["electricity"],
            i["home_consumption"],
            battery_size_input=battery_limit,  # User-provided battery capacity
            current_battery_level=cumulative_battery_size
        )
        i["battery_size"] = round(cumulative_battery_size, 2)
        sold_kw_decimal = Decimal(sold_kw)
        i["sold_kw"] = sold_kw_decimal.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        export_revenue_decimal = (sold_kw_decimal * Decimal(1000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        i["export_revenue"] = export_revenue_decimal

        # Add unsupplied energy (import kWh) to the row
        i["import_kwh"] = Decimal(str(round(unsupplied, 2)))

        # Calculate the import price using my_function
        i["import_price"] = Decimal(my_function(float(i["import_kwh"])))

        # Accumulate totals
        total_import_kwh_per_day += i["import_kwh"]
        total_import_price_per_day += i["import_price"]

        total_import_kwh += i["import_kwh"]
        total_import_price += i["import_price"]

        total_sold_energy += sold_kw_decimal  # Accumulate sold_kw

    # Ensure the last index's sold_kw and export_revenue are synchronized
    if table_info:
        last_index = table_info[-1]
        last_index["sold_kw"] += Decimal(last_index["battery_size"])
        last_index["sold_kw"] = last_index["sold_kw"].quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

        # Set export_revenue for the last index based on sold_kw * 1000
        last_index["export_revenue"] = (last_index["sold_kw"] * Decimal('1000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    # After calculating total_sold_energy:
    total_sold_energy_multiplied = total_sold_energy * Decimal('1000')

    # Calculate export info
    for i in table_info:
        i["export_info"] = round(i["battery_size"])

    final_export_info = table_info[-1]["export_info"] if table_info else 0.0

    # After your loop that accumulates sold energy:
    total_sold_energy = sum(Decimal(i["sold_kw"]) for i in table_info)

    # Example: Find the battery charge at 23:00 (if available)
    battery_charge_2300 = Decimal('0')
    for i in table_info:
        if i["time"] == "23:00":
            # For instance, suppose i["battery_size"] holds the battery charge at that time
            battery_charge_2300 = Decimal(i["battery_size"])
            break

    # Multiply the battery charge by 1000 and add to total sold energy.
    final_total_sold_energy = total_sold_energy + (battery_charge_2300 )
    final_total_sold_energy_price = (total_sold_energy *Decimal('1000')) + (battery_charge_2300 * Decimal('1000') ) 

    battery_percentage = 0  # Initialize battery percentage

    if table_info:
        last_index = table_info[-1]  # Get the last row
        # Calculate battery percentage safely
        if battery_limit > 0:
            battery_percentage = (Decimal(last_index["battery_size"]) / Decimal(battery_limit)) * 100
            battery_percentage = round(battery_percentage, 2)  # Round to 2 decimal places
        else:
            battery_percentage = 0  # Set to 0 if battery_limit is invalid

    # Example percentages for each month
    percentages = [
        9.29, 8.45, 6.60, 7.45, 8.03, 8.67, 8.95, 9.56, 7.45, 8.29, 8.52, 8.74
    ]

    # Get the current year
    year = datetime.now().year

    # Prepare a list of months, days, and calculated values
    months_and_days = []
    for index, month in enumerate([
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]):
        percentage = percentages[index]
        days = monthrange(year, index + 1)[1]
        calculated_value = 0
        daily_value = 0

        # Calculate the value if home_consumption is provided
        if home_consumption > 0:
            calculated_value = (home_consumption * (percentage / 100))
            daily_value = calculated_value / days  # Calculate daily value

        months_and_days.append({
            "month": month,
            "days": days,
            "percentage": f"{percentage}%",
            "calculated_value": round(calculated_value, 2),
            "daily_value": round(daily_value, 4)  # Add daily value
        })

    # Normalize month names in months_and_days
    for item in months_and_days:
        item["month"] = item["month"].capitalize()  # Ensure consistent capitalization

    # Hourly percentages for each month
    hourly_percentages = {
        "January": [1.0, 0.9, 0.8, 0.8, 0.8, 3.5, 10.0, 7.5, 6.5, 5.5, 5.0, 5.0, 4.9, 5.0, 5.0, 3.8, 4.2, 6.0, 6.5, 5.5, 5.5, 4.5, 3.0, 1.0],
        "February": [1.0, 0.9, 0.8, 0.8, 0.8, 3.5, 9.5, 7.0, 6.2, 5.5, 5.0, 5.0, 4.9, 5.0, 4.8, 3.8, 4.0, 6.7, 6.0, 5.5, 5.5, 5.0, 3.2, 1.0],
        "March": [1.0, 0.9, 0.8, 0.8, 0.8, 3.4, 9.5, 7.0, 6.0, 5.2, 5.0, 5.0, 5.0, 4.8, 4.6, 3.7, 3.9, 6.5, 5.9, 5.5, 5.5, 4.9, 3.0, 1.0],
        "April": [0.9, 0.8, 0.8, 0.8, 0.8, 3.5, 9.3, 7.0, 6.1, 5.4, 4.9, 5.0, 4.8, 4.7, 4.6, 3.6, 3.8, 6.6, 6.1, 5.5, 5.4, 4.9, 3.0, 1.0],
        "May": [0.7, 0.8, 0.8, 0.8, 0.7, 3.5, 9.1, 8.3, 7.1, 6.1, 5.6, 5.3, 5.0, 5.0, 4.9, 4.7, 4.6, 7.2, 6.7, 6.3, 6.1, 5.5, 3.5, 1.0],
        "June": [0.7, 0.8, 0.8, 0.7, 0.7, 3.5, 9.3, 8.4, 7.2, 6.5, 5.7, 5.5, 5.2, 5.0, 5.0, 4.8, 4.5, 7.5, 6.8, 6.5, 6.1, 5.5, 3.4, 1.0],
        "July": [0.8, 0.8, 0.8, 0.7, 0.7, 3.6, 9.2, 8.7, 7.8, 6.3, 5.5, 5.4, 5.2, 5.1, 4.9, 4.6, 4.4, 7.8, 7.1, 6.6, 6.4, 5.6, 3.5, 1.0],
        "August": [0.8, 0.8, 0.8, 0.7, 0.7, 3.6, 9.3, 8.7, 7.6, 6.0, 5.3, 5.2, 5.2, 5.1, 4.9, 4.6, 4.5, 7.7, 7.2, 6.4, 6.1, 5.6, 3.4, 1.0],
        "September": [0.8, 0.8, 0.8, 0.7, 0.7, 3.5, 9.0, 8.6, 7.7, 6.2, 5.5, 5.3, 5.2, 5.2, 5.0, 4.9, 4.6, 7.8, 7.2, 6.4, 6.1, 5.8, 3.5, 1.0],
        "October": [0.9, 0.7, 0.7, 0.7, 0.7, 3.4, 9.1, 8.8, 7.5, 6.0, 5.3, 5.2, 5.1, 5.0, 4.8, 4.5, 4.4, 7.6, 7.0, 6.2, 6.0, 5.5, 3.2, 1.0],
        "November": [0.9, 0.8, 0.8, 0.8, 0.8, 3.5, 9.0, 8.5, 7.5, 6.0, 5.5, 5.3, 5.2, 5.0, 4.8, 4.5, 4.4, 7.5, 7.0, 6.2, 6.0, 5.5, 3.2, 1.0],
        "December": [1.0, 1.0, 1.0, 1.0, 1.0, 3.5, 10.0, 7.5, 6.5, 5.5, 5.0, 5.0, 4.9, 5.0, 5.0, 3.8, 4.2, 6.0, 6.5, 5.5, 5.5, 4.5, 3.0, 1.0]
    }

    hourly_consumption_data = []

    for hour in range(24):
        hour_data = {"hour": f"{hour}:00"}
        for item in months_and_days:
            month = item["month"]
            daily_value = item["daily_value"]
            percentage = hourly_percentages[month][hour]
            hourly_value = daily_value * (percentage / 100)
            hour_data[month] = round(hourly_value, 2)  # Precalculate hourly consumption
        hourly_consumption_data.append(hour_data)

    # Calculate yearly PV generation using actual database values
    yearly_pv_generation_data_sum = 0  # Initialize yearly generation sum

    for month in [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]:
        # Query the database for the total electricity generation for the month
        monthly_generation = PvElectricity.objects.filter(month=month).aggregate(
            total_generation=Sum(F('electricity') * solar_array_size)
        )['total_generation'] or 0

        # Multiply by the number of days in the month
        days_in_month = monthrange(year, datetime.strptime(month, "%B").month)[1]
        yearly_pv_generation_data_sum += monthly_generation * days_in_month

    # Calculate yearly import price
    yearly_import_price = total_import_price  # Use the already calculated total import price

    # Initialize yearly import price
    yearly_import_price = Decimal('0')

    # List of months
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    # Iterate over each month
    sum_export_price_breakdown = [] 
    sum_import_price_breakdown = []  # Initialize an empty list to store monthly import kWh
    import_price_breakdown = []  # To store monthly breakdown

    for index, month in enumerate(months):
        # Get the number of days in the month
        days_in_month = monthrange(year, index + 1)[1]

        # Calculate the total import (kWh) for the month
        monthly_import_kwh = Decimal(total_import_kwh_per_day) * days_in_month  # Replace with actual calculation
        monthly_export_kwh = Decimal(final_total_sold_energy) * days_in_month
        # Calculate the import price using `my_function`
        monthly_import_price = Decimal(my_function(float(monthly_import_kwh)))
        monthly_export_price = Decimal(final_total_sold_energy_price) * days_in_month

        # Add to yearly total
        yearly_import_price += monthly_import_price
        yearly_export_price += monthly_export_price


        # Append to breakdown
        import_price_breakdown.append({
            "month": month,
            "days": days_in_month,
            "import_kwh": monthly_import_kwh,
            "import_price": monthly_import_price,
            "monthly_export_kwh":monthly_export_kwh,
            "monthly_export_price": monthly_export_price
        })

        # Append the monthly import kWh to the list
        sum_import_price_breakdown.append(monthly_import_kwh)
        sum_export_price_breakdown.append(monthly_export_kwh)
    # Calculate the total import kWh
    year_total_import_kwh = sum(sum_import_price_breakdown)
    year_total_export_kwh = sum(sum_export_price_breakdown)  # Total import kWh for the year

    # Pass data to the template
    return render(request, "index.html", {
        "electricity_import_cost": electricity_import_cost,
        "pv_generation_data": pv_generation_data,
        "daily_pv_generation_data_sum": daily_pv_generation_data_sum,
        "distinct_months": distinct_months,
        "distinct_times": distinct_times,
        "get_electricity_data_per_time": get_electricity_data_per_time,
        "unique_months": unique_months,
        "monthly_pv_generation_data_sum": monthly_pv_generation_data_sum,
        "home_consumption": home_consumption,
        "save_home_consumption": save_home_consumption,
        "usage_profile_result_data": usage_profile_result_data,
        "table_info": table_info,
        "final_export_info": final_export_info,
        # Pass the input values back for persistence
        "home_consumption_value": home_consumption_value,
        "solar_array_size_value": solar_array_size_value,
        "month_value": month_value,
        "usage_profile_value": usage_profile_value,
        "battery_capacity_value": battery_capacity_value,
        "total_sold_energy": total_sold_energy,  # Original sold energy sum (kW)
        "total_sold_energy_multiplied": total_sold_energy_multiplied,
        "final_total_sold_energy": final_total_sold_energy,
        "final_total_sold_energy_price": final_total_sold_energy_price,  # Final calculation
        "total_import_kwh": total_import_kwh,  # Pass the total import kWh
        "total_import_price": total_import_price,  # Pass the total import price
        "battery_percentage": battery_percentage,  # Pass the battery percentage
        "months_and_days": months_and_days,  # Pass months, days, and calculated values to the template
        "hourly_percentages": hourly_percentages,  # Pass hourly percentages to the template
        "hourly_consumption_data": hourly_consumption_data,  # Pass hourly consumption data to the template
        "yearly_pv_generation_data_sum": yearly_pv_generation_data_sum,  # Pass yearly PV generation sum to the template
        "yearly_import_price": yearly_import_price,  # Pass yearly import price to the template
        "import_price_breakdown": import_price_breakdown,
        "sum_import_price_breakdown": sum_import_price_breakdown,  # Pass the sum of import price breakdown to the template
        "total_import_price_per_day":total_import_price_per_day, 
        "total_import_kwh_per_day":total_import_kwh_per_day ,
        "year_total_import_kwh":year_total_import_kwh,  
        "yearly_export_price":yearly_export_price,
        "year_total_export_kwh":year_total_export_kwh
        
        
    })





