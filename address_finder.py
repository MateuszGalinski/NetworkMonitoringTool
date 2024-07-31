import paramiko
import pandas as pd
import time
import os
import glob
from datetime import datetime

import paramiko.ssh_exception

def get_groups_file(path : str = 'switch_groups.txt') -> pd.DataFrame:
    """Ta funkcja pobiera plik z grupami i dodaje mu pola na dane logowania
    Argumenty:
    - path : String - ścieżka do pliku może być relatywna bądź absolutna

    Zwraca:
    - switch_groups : pd.DataFrame - tabela z numerami grup i podpowiedziami do nich
    """
    switch_groups = pd.read_csv(path, sep='\t')
    switch_groups["login"] = None
    switch_groups["password"] = None
    return switch_groups

def get_ips_file(path : str = 'switch_ips.txt') -> pd.DataFrame:
    """Ta funkcja pobiera plik z adresami ip
    Argumenty:
    - path : String - ścieżka do pliku może być relatywna bądź absolutna

    Zwraca:
    - switch_ips : pd.DataFrame - tabela z adresami ip, nazwami oraz numerami grup poszczególnych switchy
    """
    switch_ips = pd.read_csv(path, sep='\t')
    return switch_ips

def get_interfaces_file(path : str = 'interfaces.txt') -> pd.DataFrame:
    """Ta funkcja pobiera plik z adresami ip
    Argumenty:
    - path : String - ścieżka do pliku może być relatywna bądź absolutna

    Zwraca:
    - interfaces_list : pd.DataFrame - tabela z interfejsami i ich opisami
    """
    interfaces_list = pd.read_csv(path, sep='\t')
    return interfaces_list

def get_devices_file(path : str = 'Krok1_przyklad_tab.csv') -> pd.DataFrame:
    """Ta funkcja pobiera plik z adresami ip
    Argumenty:
    - path : String - ścieżka do pliku może być relatywna bądź absolutna

    Zwraca:
    - devices_list : pd.DataFrame - tabela z urządzeniami w tym ich adresami ip, mac, dostawcami oraz nazwami interfejsów
    """
    devices_list = pd.read_csv(path, sep='\t')
    return devices_list

def assign_credentials_to_groups(switch_groups : pd.DataFrame):
    """Funkcja przechodzi przez tabelę grup i prosi użytkownika o wpisanie loginu oraz hasła do każdej grupy
    Argumenty:
    - switch_groups : pd.DataFrame - tabela grup, do której przypisane mają być dane logowania   
    """
    for index, row in switch_groups.iterrows():
        group = row['group']
        hint = row['hint']
        password = None
        login = None

        while not login:
            login = input(f"Wprowadz login do switchy z grupy {group} (podpowiedz: ({hint})): ")
            if not login:
                print("Login pusty, proszę wprowadz ponownie")

        while not password:
            password = input(f"Wprowadz haslo do switchy z grupy {group} (podpowiedz: ({hint})): ")
            if not password:
                print("Haslo puste, prosze wprowadz ponownie")
    
        switch_groups.at[index, 'login'] = login
        switch_groups.at[index, 'password'] = password

def get_mac_table_from_ssh(ssh : paramiko.SSHClient) -> pd.DataFrame:
    """Funkcja pozyskuje tabelę adresów Mac z wybranego serwera ssh
    Argumenty:
    - ssh : paramiko.SSHClient - instancja klienta ssh z istniejącym połączeniem do serwera

    Zwraca:
    -mac_table : pd.DataFrame - tablica adresów mac z columnami [vlan, mac address, type, ports]
    """
    stdin, stdout, stderr = ssh.exec_command('sh mac address-table | exclude (Po|Vl|CPU)')

    data = stdout.read().decode('utf-8')
    
        # Split the string into lines
    lines = data.strip().split('\n')

    # Remove header and separators
    lines = [line for line in lines if not line.startswith(('Mac Address Table', '-------------------------------------------', 'Vlan    Mac Address       Type        Ports', '----    -----------       --------    -----'))]

    # Define columns
    columns = ['vlan', 'mac address', 'type', 'ports']

    mac_table = pd.DataFrame(columns=columns)

    # Parse each line and extract the columns
    for line in lines:
        words = line.strip().split()
        if len(words) > 0 and words[0] != 'Total': #this is condition to get rid of first empty line and last summary line
            row = {'vlan': words[0], 'mac address': words[1], 'type': words[2], 'ports': words[3]}
            mac_table.loc[len(mac_table)] = row

    return mac_table

def get_all_mac_table(merged_table : pd.DataFrame) -> pd.DataFrame:
    """
    Argumenty:
    - merged_table : pd.DataFrame - tabela będąca połączeniem switch_ips i group_ips, posiadająca dane logowania, nazwę i ip switchy
    Zwraca:
    - all_macs_table : pd.DataFrame - tabela zawierająca wszystkie addressy mac, wszystkich switchy 
    """
    all_macs_table = pd.DataFrame()

    for index, row in merged_table.iterrows():
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(row['ip'], username=row["login"], password=row["password"])
            mac_table = get_mac_table_from_ssh(ssh)
            mac_table['swt'] = row['swt']
            mac_table['ip'] = row['ip']
            all_macs_table = pd.concat([all_macs_table, mac_table])
            ssh.close()
        except:
            print(f"Błąd połączenia ze switchem {row["swt"]} o ip {row["ip"]}")
            raise RuntimeError('Błąd połączenia', row["swt"], row["ip"])

    return all_macs_table

def compare_tables(df_old : pd.DataFrame, df_new : pd.DataFrame) -> pd.DataFrame:
    """Porównuje tabele df_old oraz df_new i generuje tabelę raportującą z dodatkową columną state, 
    tabele MUSZĄ mieć IDENTYCZNE kolumny w celu działania tej funkcji
    Argumenty:
    - df_old : pd.DataFrame - tabela chronologicznie starsza
    - df_new : pd.DataFrame - tabela chronologicznie nowsza
    Zwraca:
    - result_df : pd.DataFrame - tabela raport w formacie [kolumy_wejsciowe, ..., state], gdzie state może być removed bądź added"""
    if df_old.equals(df_new):
        print("THEY ARE EQUAL!!!")
    
    removed_df = df_old[~df_old.isin(df_new.to_dict(orient='list')).all(axis=1)].copy()
    removed_df['state'] = 'removed'
    
    added_df = df_new[~df_new.isin(df_old.to_dict(orient='list')).all(axis=1)].copy()
    added_df['state'] = 'added'

    result_df = pd.concat([removed_df, added_df])

    
    return result_df

def normalize_mac(mac):
    """Funkcja do zmiany adresów mac na wspólny format"""
    return mac.replace('.', '').replace(':', '').lower()

def create_full_devices_list_table(all_macs_table : pd.DataFrame, devices_list : pd.DataFrame, interfaces_list : pd.DataFrame) -> pd.DataFrame:
    """Funkcja tworzy spis wszystkich urzadzen z ich interfejsami, przypisanymi do nich switchami, adresami mac itd
    Argumenty:
    - all_macs_table : pd.DataFrame - tablica ze wszystkimi adresami mac jakie są podpiete do switchy
    - devices_list : pd.DataFrame - tablica oczekiwanych urzadzen z ich macami, adresami ip i dostawcami
    - interfaces_list - lista istniejacych interfejsow z ich opisami"""
    all_macs_table['mac address'] = all_macs_table['mac address'].apply(normalize_mac)
    devices_list['MAC'] = devices_list['MAC'].apply(normalize_mac)
    merged_df = pd.merge(all_macs_table, devices_list, left_on=['mac address'], right_on=['MAC'], how='left')
    merged_df = merged_df.drop(columns={'MAC'})
    current_device_list_full = pd.merge(merged_df, interfaces_list, on=['Interfejs'], how='left')
    current_device_list_full = current_device_list_full.rename(columns={"IP": "ip urzadzenia", "ip": "ip swt"})
    return current_device_list_full

def find_latest_report(directory : str = ''):
    # Pattern for the files to search
    pattern = os.path.join(directory, 'lista_urzadzen_*.csv')

    # Get a list of all files matching the pattern
    files = glob.glob(pattern)

    # Initialize variables to keep track of the latest file and its timestamp
    latest_file = None
    latest_time = None

    # Iterate over the files to find the latest one
    for file in files:
        # Extract the filename from the path
        filename = os.path.basename(file)
        
        # Extract the timestamp from the filename
        timestamp_str = filename.replace('lista_urzadzen_', '').replace('.csv', '')
        
        try:
            # Parse the timestamp string to a datetime object
            file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
        except ValueError:
            # If timestamp parsing fails, skip the file
            print(f"Skipping file with invalid timestamp format: {filename}")
            continue
        
        # Update latest file if this file is more recent
        if latest_time is None or file_time > latest_time:
            latest_file = file
            latest_time = file_time

    return latest_file

def file_exists(filename : str = 'ostatnia_lista_urzadzen.csv', directory : str = ''):
    # Construct the full path of the file
    file_path = os.path.join(directory, filename)
    
    # Check if the file exists
    return os.path.isfile(file_path)


def main():
    #----------------------- Section that creates a list of all mac tables of switches specified in ips file -------------------------
    
    program_start = time.time()
    switch_groups = get_groups_file()
    # print(switch_groups)
    switch_ips = get_ips_file("correct_ips.txt")
    # print(switch_ips)
    assign_credentials_to_groups(switch_groups)
    merged_df = pd.merge(switch_ips, switch_groups[['group', 'login', 'password']], on='group', how='left') # Mergowanie grup i ip
    # print(merged_df)
    try:
        all_mac_table = get_all_mac_table(merged_df)
    except RuntimeError as e:
       print(f"Error parameters: {e.args}")   
       print("Koniec programu")
       return # Kończy program przedwcześnie przy jakichkolwiek problemach z łączeniem
    
    # all_mac_table.to_csv(time.strftime('%Y-%m-%d_%H-%M-%S.csv', time.localtime(program_start)), sep='\t', index=False)
    interfaces_list = get_interfaces_file()
    devices_list = get_devices_file()
    current_full_device_list_table = create_full_devices_list_table(all_mac_table, devices_list, interfaces_list)
    current_full_device_list_table.to_csv(time.strftime('devices_lists/lista_urzadzen_%Y%m%d_%H%M%S.csv', time.localtime(program_start)), sep='\t', index=False)

    #-------------------------- Section that compares reports -----------------------------------

    # all_mac_table = pd.read_csv('2024-07-30_15-37-08.csv', sep='\t')
    # old_report = pd.read_csv('last_report_example.csv', sep='\t')
    # interfaces_list = get_interfaces_file()
    # devices_list = get_devices_file()
    # full_device_list_table = create_full_devices_list_table(all_mac_table, devices_list, interfaces_list)
    # print(compare_tables(old_report, full_device_list_table))

    #-------------------------- Section testing files -------------------------

    if not file_exists('ostatnia_lista_urzadzen.csv'):
        current_full_device_list_table.to_csv("ostatnia_lista_urzadzen.csv", sep='\t', index=False)

    last_devices_list = pd.read_csv("ostatnia_lista_urzadzen.csv", sep='\t')
    current_full_device_list_table = pd.read_csv(time.strftime('devices_lists/lista_urzadzen_%Y%m%d_%H%M%S.csv', time.localtime(program_start)), sep='\t', encoding='utf-8')

    comparision_report = compare_tables(last_devices_list, current_full_device_list_table)

    current_full_device_list_table.to_csv("ostatnia_lista_urzadzen.csv", sep='\t', index=False)
    comparision_report.to_csv(time.strftime('reports/raport_%Y%m%d_%H%M%S.csv', time.localtime(program_start)), sep='\t', index=False)

    input_to_total_history = comparision_report
    input_to_total_history["date"] = time.strftime('%Y/%m/%d_%H:%M:%S', time.localtime(program_start))
    
    input_to_total_history.to_csv("totalny_changelog.csv", sep = '\t', mode='a', header=not file_exists('totalny_changelog.csv'))

if __name__ == "__main__":
    main()