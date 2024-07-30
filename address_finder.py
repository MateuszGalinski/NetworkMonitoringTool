import paramiko
import pandas as pd
import time

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
            all_macs_table = pd.concat([all_macs_table, mac_table])
        except:
            print(f"Błąd połączenia ze switchem {row["swt"]} o ip {row["ip"]}")
            raise RuntimeError('Błąd połączenia', row["swt"], row["ip"])

    return all_macs_table

def main():
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
    
    print(all_mac_table)
    all_mac_table.to_csv(time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(program_start)), sep='\t', )

if __name__ == "__main__":
    main()